"""Kill flag at the side-effecting capability checkout (Chapter 7.2 T1).

**The mechanism (research §6, "kill flag checked before every tool call").**
A real kill switch is infra-level revocation re-checked *before every
side-effecting call*, not a prompt instruction or a UI button. In this
codebase the per-call gate is `engine.capabilities.lease_service.
CapabilityLeaseService.require_active` -- the one guard both real Stage 1
side-effecting call sites (`ScriptedWorkerAdapter.start` for filesystem +
local-process, `WorkspaceService.snapshot` for git) already pass through,
per call. This module adds a run-scoped kill flag to exactly that checkout:
once set for a `(tenant_id, project_id, worker_run_id)`, every subsequent
`require_active` for that run fails closed with typed `KILL_FLAG_ACTIVE`,
and the first successful checkout after arming records the stop durably on
the existing lease rows -- no new table, no new state-machine status.

**What is wired here vs disclosed as unwired.**
- Wired: arming goes through the service layer -- `engine.capabilities.
  lease_service.CapabilityLeaseService.arm_run_stop` registers the flag AND
  performs an ACTIVE sweep in one transaction: every still-held lease of
  the run transitions to the chapter-named terminal status `REVOKED` with
  `revocation_reason="kill_flag"`, and ONE summary event is journaled. The
  caller composing the stop pairs it with `CredentialBrokerService.
  revoke_handles_for_leases` in the same unit of work so live handles die
  at arm time too. The durable half of an intentional stop therefore
  exists at arm time; it does not wait for (nor depend on) a later
  refused call.
- Wired (durable): the ARMED/DISARMED state itself is persisted through
  the EXISTING `command_idempotency` table (Chapter 3.7) via
  `engine.events.idempotency.CommandLedger` -- no new table, no schema
  change. One ledger row per run, keyed `kill_flag_run_stop:{run_id}`;
  `arm_run_stop`/`disarm_run_stop` create-or-flip it inside the
  transaction they already open, and the two enforcement sites consult it
  (memory first, then the row) inside the unit of work they already hold,
  so a fresh process with a cold registry still refuses for a stopped run.
- Wired: both refusal surfaces journal their enforcement -- a checkout
  refusal emits `CapabilityKillFlagEnforced` and a credential-admission
  refusal emits `CredentialKillFlagEnforced`, committed atomically with
  their surrounding unit of work, so the audit trail shows every gate
  actually firing even when the sweep already emptied the run's held set.
- Wired: `require_active` keeps its own "revoke still-held leases on first
  refusal" behaviour purely as a BACKSTOP for leases granted between arm
  and the next checkout; the sweep-on-arm is primary.
- NOT wired (named honestly): network egress is not gated by this flag.
  The recovery matrix's distinct intentionally-stopped attribution
  (research: "lands as INTENTIONALLY_STOPPED, not FAILED") does not exist
  in Chapter 12.3's taxonomy; the matrix maps `WORKER_CAPABILITY_DENIED`
  -> AUTHORIZATION_FAILURE -> request_approval/requires_human, which is
  where a killed run's attempt lands today -- adopting a new matrix row
  would be a Project Truth change, proposed, not made here.
- Remaining honest limits: an already-in-flight subprocess cannot be
  interrupted mid-call (T2 containment, DDE-018) and network egress is
  still ungated (T2 EDR); the in-memory registry remains a per-instance
  cache of the durable row, not a second source of truth.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING
from uuid import UUID

from engine.core.hashing import canonical_json, sha256_hex

if TYPE_CHECKING:
    from engine.events.idempotency import CommandLedger
    from engine.truth.db import PostgresUnitOfWork

KILL_FLAG_REASON = "kill_flag"

#: Journal names for the two enforcement surfaces. Event types are open
#: convention strings (`schemas/events/core_event.json`: free-form
#: `event_type`, open `payload`); these follow the existing
#: `CapabilityLease*`/`Credential*` naming families.
CHECKOUT_ENFORCEMENT_EVENT_TYPE = "CapabilityKillFlagEnforced"
ADMISSION_ENFORCEMENT_EVENT_TYPE = "CredentialKillFlagEnforced"
RUN_STOP_ARMED_EVENT_TYPE = "CapabilityRunStopArmed"

#: Durable stop-record state values carried in the ledger row's `result`
#: JSONB (`{"state": ..., "reason": ...}`). The row's own ledger `status`
#: stays `completed` -- the stop state lives in the result payload, not a
#: second status taxonomy.
STOP_STATE_ARMED = "ARMED"
STOP_STATE_DISARMED = "DISARMED"


def run_stop_idempotency_key(worker_run_id: UUID) -> str:
    """The one deterministic ledger key per run's stop record. Both
    writers (`arm_run_stop`, `disarm_run_stop`) and both enforcement
    readers resolve the same single row through this -- no second key
    format may exist."""
    return f"kill_flag_run_stop:{worker_run_id}"


def _stop_result(state: str, reason: str) -> dict[str, object]:
    return {"state": state, "reason": reason}


def _stop_state(record_result: object) -> str | None:
    """Extract the stop state from a ledger row's `result` payload;
    `None` for a row this mechanism did not write (defensive -- the key
    namespace above is owned by this module)."""
    if isinstance(record_result, dict):
        state = record_result.get("state")
        if state == STOP_STATE_ARMED:
            return STOP_STATE_ARMED
        if state == STOP_STATE_DISARMED:
            return STOP_STATE_DISARMED
    return None


async def read_durable_run_stop(
    ledger: CommandLedger,
    *,
    tenant_id: UUID,
    project_id: UUID,
    worker_run_id: UUID,
    uow: PostgresUnitOfWork,
) -> bool:
    """Whether the DURABLE stop record says the run is stopped. Must be
    called inside a unit of work the caller already holds (both
    enforcement sites do); opens none of its own."""
    record = await ledger.get_by_key_scoped(
        tenant_id=tenant_id,
        project_id=project_id,
        idempotency_key=run_stop_idempotency_key(worker_run_id),
        uow=uow,
    )
    if record is None:
        return False
    return _stop_state(record.result) == STOP_STATE_ARMED


async def record_run_stop(
    ledger: CommandLedger,
    *,
    tenant_id: UUID,
    project_id: UUID,
    worker_run_id: UUID,
    armed: bool,
    reason: str,
    uow: PostgresUnitOfWork,
) -> None:
    """Create-or-flip the run's durable stop record through the ledger's
    existing `begin` (insert-once, request-hash-guarded) and `complete`
    (status/result update) API -- the exact idempotency machinery
    `CapabilityLeaseService.request` already uses, not a second one.
    `begin`'s dedup makes a repeated arm/disarm with the same key a
    no-op on insert; `complete` flips the recorded state. Must be called
    inside a unit of work the caller already holds."""
    record, _is_new = await ledger.begin(
        tenant_id=tenant_id,
        project_id=project_id,
        idempotency_key=run_stop_idempotency_key(worker_run_id),
        request_hash=sha256_hex(
            canonical_json({"worker_run_id": str(worker_run_id), "kind": "run_stop"})
        ),
        uow=uow,
    )
    await ledger.complete(
        tenant_id=tenant_id,
        project_id=project_id,
        command_id=record.command_id,
        result=_stop_result(STOP_STATE_ARMED if armed else STOP_STATE_DISARMED, reason),
        uow=uow,
    )


class KillSwitchRegistry:
    """In-memory, thread-safe registry of killed worker runs. Deliberately
    tiny: it is the fast per-process cache in front of the durable stop
    record (`record_run_stop`/`read_durable_run_stop`), not a second
    source of truth -- the ledger row is what survives a restart."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._killed: set[tuple[UUID, UUID, UUID]] = set()

    def arm(self, *, tenant_id: UUID, project_id: UUID, worker_run_id: UUID) -> None:
        with self._lock:
            self._killed.add((tenant_id, project_id, worker_run_id))

    def is_killed(
        self, *, tenant_id: UUID, project_id: UUID, worker_run_id: UUID
    ) -> bool:
        with self._lock:
            return (tenant_id, project_id, worker_run_id) in self._killed

    def disarm(self, *, tenant_id: UUID, project_id: UUID, worker_run_id: UUID) -> None:
        """Drop this instance's in-memory flag only. The DURABLE undo of a
        stop is `CapabilityLeaseService.disarm_run_stop`, which flips the
        ledger row AND calls this; dropping the cache alone never
        resurrects authority while the durable record says ARMED."""
        with self._lock:
            self._killed.discard((tenant_id, project_id, worker_run_id))
