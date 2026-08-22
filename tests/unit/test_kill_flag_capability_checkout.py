"""Kill flag at capability checkout (research §6 item 2) -- pure unit tests
over the real `CapabilityLeaseService.require_active` gate logic with fake
repositories/events, no PostgreSQL.

Production call sites under test: `engine.capabilities.lease_service.
CapabilityLeaseService.require_active` is THE per-call guard both real
Stage 1 side-effecting paths pass through (`engine.workers.scripted_adapter.
ScriptedWorkerAdapter.start` for filesystem/local-process and
`engine.workspaces.service.WorkspaceService.snapshot` for git). The kill
flag is checked inside that checkout's transaction: arming a stop for a run
takes effect before the run's NEXT tool call, not at attempt start. The
first refused checkout durably transitions the run's most recent still-held
lease to the chapter-named terminal status REVOKED with reason "kill_flag"
-- the closest existing Chapter 9.2 state, no new taxonomy invented.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from engine.capabilities.kill_switch import KILL_FLAG_REASON, KillSwitchRegistry
from engine.capabilities.lease_repository import CapabilityLeaseRepository
from engine.capabilities.lease_service import CapabilityLeaseService
from engine.contracts.capability_lease import CapabilityLease
from engine.core.errors import DdeError

TENANT = uuid4()
PROJECT = uuid4()
RUN = uuid4()


class RecordingEvents:
    """No-op stand-in for `engine.events.service.EventService.append` --
    the only member `_transition` uses on the events service. Records
    calls so tests can assert a revocation actually emitted its event."""

    def __init__(self) -> None:
        self.appended: list[dict[str, object]] = []

    async def append(self, **kwargs: object) -> None:
        self.appended.append(dict(kwargs))


class FakeLeaseRepository(CapabilityLeaseRepository):
    """In-memory stand-in for the lease row store; only the members the
    kill-flag path and `require_active` touch are overridden. The base
    class is subclassed so any member this file forgets to fake fails
    loudly instead of silently passing."""

    def __init__(self, leases: list[CapabilityLease]) -> None:
        self.leases = leases
        self.updates: dict[str, object] = {}

    async def get_active_for_run(
        self,
        connection: object,
        *,
        worker_run_id: object,
        capability_id: str,
    ) -> CapabilityLease | None:
        candidates = [
            item
            for item in self.leases
            if item.worker_run_id == worker_run_id
            and item.capability_id == capability_id
        ]
        return candidates[-1] if candidates else None

    async def list_for_run(
        self, connection: object, worker_run_id: object
    ) -> list[CapabilityLease]:
        return [item for item in self.leases if item.worker_run_id == worker_run_id]

    async def get_by_id(
        self, connection: object, lease_id: object
    ) -> CapabilityLease | None:
        for item in self.leases:
            if item.lease_id == lease_id:
                return item
        return None

    async def update_fields(
        self,
        connection: object,
        lease_id: object,
        *,
        fields: dict[str, object],
    ) -> int:
        for index, item in enumerate(self.leases):
            if item.lease_id == lease_id:
                data = item.model_dump()
                data.update(fields)
                self.leases[index] = CapabilityLease.model_validate(data)
                self.updates[str(lease_id)] = dict(fields)
                return 1
        return 0


class FakeUOW:
    """`require_active`'s body never touches the connection when the
    repository is faked; it is passed through opaquely."""

    connection = object()

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def _lease(
    *, status: str, capability_id: str = "capability.run_local_process"
) -> CapabilityLease:
    now = datetime.now(UTC)
    return CapabilityLease(
        lease_id=uuid4(),
        tenant_id=TENANT,
        project_id=PROJECT,
        mission_id=uuid4(),
        task_id=uuid4(),
        execution_plan_id=uuid4(),
        worker_run_id=RUN,
        environment_id=None,
        capability_id=capability_id,
        capability_version="1",
        resource_scope={},
        operation_scope="execute",
        constraints={},
        issued_by_policy_version="capability-lease-v1",
        issued_at=now,
        expires_at=now + timedelta(hours=24),
        revocable=True,
        status=status,
        denied_reason=None,
        revoked_at=None,
        revocation_reason=None,
        lease_hash="hash",
        requested_by="test",
        created_at=now,
        updated_at=now,
    )


def _service(
    leases: list[CapabilityLease],
) -> tuple[CapabilityLeaseService, FakeLeaseRepository, RecordingEvents]:
    repo = FakeLeaseRepository(leases)
    events = RecordingEvents()
    service = CapabilityLeaseService(
        engine=None,  # type: ignore[arg-type]
        repository=repo,
        events=events,  # type: ignore[arg-type]
        commands=None,  # type: ignore[arg-type]
        capabilities=None,  # type: ignore[arg-type]
        kill_switch=KillSwitchRegistry(),
    )
    return service, repo, events


async def test_armed_kill_flag_refuses_checkout_of_a_held_lease() -> None:
    """Mid-run revocation: the lease was GRANTED (or even already ACTIVE --
    the state a previous successful tool call left it in), then the kill
    switch arms. The very next checkout must fail closed with typed
    KILL_FLAG_ACTIVE -- exactly like an expiry does, but with its own code
    so an intentional stop is distinguishable from a policy denial."""
    lease = _lease(status="ACTIVE")
    service, repo, events = _service([lease])
    service.kill_switch.arm(tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN)

    with pytest.raises(DdeError) as excinfo:
        await service.require_active(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            capability_id="capability.run_local_process",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
    assert excinfo.value.error_code == "KILL_FLAG_ACTIVE"
    assert excinfo.value.details is not None
    assert excinfo.value.details["reason"] == KILL_FLAG_REASON
    assert len(events.appended) == 1
    assert events.appended[0]["event_type"] == "CapabilityLeaseRevoked"


async def test_first_refusal_durably_revokes_latest_held_lease() -> None:
    """The durable half of the intentional stop uses the closest existing
    state: EVERY still-held lease of the run lands in the chapter-named
    terminal status REVOKED with reason kill_flag -- so the stop survives
    process restarts even though the flag set itself does not."""
    older = _lease(status="ACTIVE")
    newer = _lease(status="GRANTED", capability_id="capability.workspace_filesystem")
    service, repo, _events = _service([older, newer])
    service.kill_switch.arm(tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN)

    with pytest.raises(DdeError) as excinfo:
        await service.require_active(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            capability_id="capability.run_local_process",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
    assert excinfo.value.error_code == "KILL_FLAG_ACTIVE"
    statuses = {item.lease_id: item.status for item in repo.leases}
    assert statuses[older.lease_id] == "REVOKED"
    assert statuses[newer.lease_id] == "REVOKED"
    stored = repo.updates[str(older.lease_id)]
    assert isinstance(stored, dict)
    assert stored["revocation_reason"] == KILL_FLAG_REASON


async def test_kill_refusal_persists_across_disarm_is_not_possible_via_checkout() -> (
    None
):
    """After the first refusal revoked the held lease, a later checkout of
    the same run/capability still fails closed even if the caller somehow
    re-requests it -- REVOKED is terminal in Chapter 9.2's machine. This is
    the adversarial check from the mission-chapter-gate rule: no new
    checkout path resurrects authority."""
    lease = _lease(status="ACTIVE")
    service, repo, _events = _service([lease])
    service.kill_switch.arm(tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN)

    with pytest.raises(DdeError):
        await service.require_active(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            capability_id="capability.run_local_process",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )

    # Simulate a restarted process where the in-memory flag set is empty:
    # the durable REVOKED row must still fail the run closed.
    service.kill_switch.disarm(tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN)
    with pytest.raises(DdeError) as excinfo:
        await service.require_active(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            capability_id="capability.run_local_process",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
    assert excinfo.value.error_code == "POLICY_DENIED"
    assert "not held" in excinfo.value.message


async def test_kill_flag_for_one_run_does_not_touch_other_runs() -> None:
    """Scope discipline: arming a stop for one worker run must not refuse
    another run's checkout."""
    killed_run = RUN

    class ScopedRepo(FakeLeaseRepository):
        async def get_active_for_run(
            self,
            connection: object,
            *,
            worker_run_id: object,
            capability_id: str,
        ) -> CapabilityLease | None:
            if worker_run_id != RUN:
                return None
            return await super().get_active_for_run(
                connection,
                worker_run_id=worker_run_id,
                capability_id=capability_id,
            )

    repo = ScopedRepo([_lease(status="ACTIVE")])
    events = RecordingEvents()
    service = CapabilityLeaseService(
        engine=None,  # type: ignore[arg-type]
        repository=repo,
        events=events,  # type: ignore[arg-type]
        commands=None,  # type: ignore[arg-type]
        capabilities=None,  # type: ignore[arg-type]
        kill_switch=KillSwitchRegistry(),
    )
    service.kill_switch.arm(
        tenant_id=TENANT, project_id=PROJECT, worker_run_id=killed_run
    )
    with pytest.raises(DdeError):
        await service.require_active(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=killed_run,
            capability_id="capability.run_local_process",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )


async def test_unarmed_service_behaviour_is_unchanged() -> None:
    """The default path (no kill switch armed anywhere) must behave
    byte-identically to before this change: GRANTED activates on first
    checkout, expiry still wins over everything else."""
    granted = _lease(status="GRANTED")
    service, repo, events = _service([granted])

    activated = await service.require_active(
        tenant_id=TENANT,
        project_id=PROJECT,
        worker_run_id=RUN,
        capability_id="capability.run_local_process",
        uow=FakeUOW(),  # type: ignore[arg-type]
    )
    assert activated.status == "ACTIVE"
    assert repo.updates[str(granted.lease_id)]["status"] == "ACTIVE"
    assert len(events.appended) == 1
    assert events.appended[0]["event_type"] == "CapabilityLeaseActivated"


async def test_kill_flag_with_no_existing_lease_still_fails_closed() -> None:
    """A run killed before any lease exists has no row to stamp -- the
    refusal must still happen (fail closed), with nothing fabricated."""
    service, _repo, _events = _service([])
    service.kill_switch.arm(tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN)

    with pytest.raises(DdeError) as excinfo:
        await service.require_active(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            capability_id="capability.run_local_process",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
    assert excinfo.value.error_code == "KILL_FLAG_ACTIVE"


def test_recovery_matrix_maps_kill_refusal_to_authorization_failure() -> None:
    """A mid-run kill refusal that reaches recovery dispatches onto the
    closest existing taxonomy row: AUTHORIZATION_FAILURE (request_approval,
    requires_human, never silently retried). Chapter 12.3 names no distinct
    intentionally-stopped class; adopting one would be a Project Truth
    change, proposed not made -- this pins the honest mapping instead."""
    from engine.recovery.matrix import canonical_failure_class, decide

    assert canonical_failure_class("KILL_FLAG_ACTIVE") == "AUTHORIZATION_FAILURE"
    decision = decide("KILL_FLAG_ACTIVE", occurrence_count=1)
    assert decision.allow_new_worker_run is False
    assert decision.requires_human is True
    assert decision.action == "request_approval"
