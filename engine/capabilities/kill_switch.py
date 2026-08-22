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
- Scope: the flag lives in the service process's memory. It is effective
  for any caller going through this service instance (the single writer of
  `capability_leases`) but is not itself persisted across process restarts;
  the durable REVOKED rows and revoked handles are what survive. A
  cross-process flag store would need infrastructure Chapter 9 does not
  name -- a ledger-backed stop record is the planned durable replacement,
  deferred until chartered.
"""

from __future__ import annotations

import threading
from uuid import UUID

KILL_FLAG_REASON = "kill_flag"

#: Journal names for the two enforcement surfaces. Event types are open
#: convention strings (`schemas/events/core_event.json`: free-form
#: `event_type`, open `payload`); these follow the existing
#: `CapabilityLease*`/`Credential*` naming families.
CHECKOUT_ENFORCEMENT_EVENT_TYPE = "CapabilityKillFlagEnforced"
ADMISSION_ENFORCEMENT_EVENT_TYPE = "CredentialKillFlagEnforced"
RUN_STOP_ARMED_EVENT_TYPE = "CapabilityRunStopArmed"


class KillSwitchRegistry:
    """In-memory, thread-safe registry of killed worker runs. Deliberately
    tiny: the durable half of an intentional stop belongs to the REVOKED
    lease rows and revoked credential handles written by
    `CapabilityLeaseService.arm_run_stop`'s sweep, not to a second source
    of truth here."""

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
        """Test/operator escape hatch only. A production stop is undone by
        issuing a NEW lease for a new run, never by un-killing a killed
        one -- kept explicit rather than hidden so no code path can
        silently resurrect authority."""
        with self._lock:
            self._killed.discard((tenant_id, project_id, worker_run_id))
