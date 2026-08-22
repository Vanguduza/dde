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
`require_active` for that run fails closed with typed
`KILL_FLAG_ACTIVE`, and the first successful checkout after arming records
the stop durably on the existing lease row -- no new table, no new state-
machine status.

**What is wired here vs disclosed as unwired.**
- Wired: the flag is consulted inside `require_active`'s own transaction
  (`_op`), so a mid-run `arm()` takes effect before the run's NEXT tool
  call -- the same granularity the lease module already documents for
  mid-run revocation ("no per-syscall interception without T2 containment;
  an already-in-flight uninterruptible subprocess cannot be interrupted").
- Wired: durable intent via the closest existing state -- the run's most
  recent lease is transitioned to the chapter-named terminal status
  `REVOKED` with `revocation_reason="kill_flag"`. The Chapter 9.2 state
  machine already treats `REVOKED` as fail-closed forever; nothing new is
  invented. If no lease exists yet, only the in-memory flag is set (there
  is no row to stamp).
- NOT wired (named honestly): network egress / broker credential paths are
  separate admission surfaces and are not gated by this flag;
  `CredentialBrokerService._require_active_lease` reads live rows directly
  and does not consult it. The recovery matrix's distinct
  intentionally-stopped attribution (research: "lands as INTENTIONALLY_
  STOPPED, not FAILED") does not exist in Chapter 12.3's taxonomy; the
  matrix maps `WORKER_CAPABILITY_DENIED` -> AUTHORIZATION_FAILURE ->
  request_approval/requires_human, which is where a killed run's attempt
  lands today -- adopting a new matrix row would be a Project Truth change,
  proposed, not made here.
- Scope: the flag lives in the service process's memory. It is effective
  for any caller going through this service instance (the single writer of
  `capability_leases`) but is not itself persisted across process restarts;
  the durable REVOKED row is what survives. A cross-process flag store
  would need infrastructure Chapter 9 does not name.
"""

from __future__ import annotations

import threading
from uuid import UUID

KILL_FLAG_REASON = "kill_flag"


class KillSwitchRegistry:
    """In-memory, thread-safe registry of killed worker runs. Deliberately
    tiny: the durable half of an intentional stop belongs to the lease row,
    not to a second source of truth here."""

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
