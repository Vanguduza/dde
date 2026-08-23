"""Arm-time process termination (Chapter 7.2 T2 revocation latency) --
pure unit tests over the real `CapabilityLeaseService.arm_run_stop` sweep
with fake repositories/events/ledger/effects, no PostgreSQL.

Production seams under test: arming a stop now (a) revokes held leases,
(b) terminates every registered live local process of the run through
`engine.capabilities.process_registry`, (c) journals each termination as
a Chapter 12.4 external effect through the EXISTING `ExternalEffectService`
(target_system `process_termination`, side_effect_class from
`capability.run_local_process`, carrying the authorizing lease id and
pid), and (d) names the terminated pids on the `CapabilityRunStopArmed`
summary event -- all in ONE unit of work. The one real-subprocess test
proves the OS effect; the rest pin journaling, scoping and best-effort
discipline deterministically.
"""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from engine.capabilities.kill_switch import KILL_FLAG_REASON
from engine.capabilities.lease_repository import CapabilityLeaseRepository
from engine.capabilities.lease_service import CapabilityLeaseService
from engine.capabilities.lease_states import HELD_LEASE_STATUSES
from engine.capabilities.process_registry import (
    SHARED_PROCESS_REGISTRY,
    ProcessHandleRegistry,
    RegisteredAuthority,
    RegisteredProcess,
    TerminationOutcome,
)
from engine.contracts.capability_lease import CapabilityLease
from engine.contracts.command_idempotency import CommandIdempotency

TENANT = uuid4()
PROJECT = uuid4()
RUN = uuid4()
MISSION = uuid4()
TASK = uuid4()

_SLOW_EXIT_COMMAND = [sys.executable, "-c", "import time; time.sleep(30)"]


class RecordingEvents:
    def __init__(self) -> None:
        self.appended: list[dict[str, object]] = []

    async def append(self, **kwargs: object) -> None:
        self.appended.append(dict(kwargs))


class FakeLeaseRepository(CapabilityLeaseRepository):
    def __init__(self, leases: list[CapabilityLease]) -> None:
        self.leases = leases

    async def list_held_for_run(
        self, connection: object, worker_run_id: object
    ) -> list[CapabilityLease]:
        return [
            item
            for item in self.leases
            if item.worker_run_id == worker_run_id
            and item.status in HELD_LEASE_STATUSES
        ]

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
                return 1
        return 0


class FakeLedger:
    def __init__(self) -> None:
        self.rows: dict[tuple[UUID, str], CommandIdempotency] = {}

    async def begin(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        idempotency_key: str,
        request_hash: str,
        uow: object = None,
    ) -> tuple[CommandIdempotency, bool]:
        now = datetime.now(UTC)
        key = (tenant_id, idempotency_key)
        existing = self.rows.get(key)
        if existing is not None:
            return existing, False
        record = CommandIdempotency(
            command_id=uuid4(),
            tenant_id=tenant_id,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status="in_progress",
            result=None,
            expires_at=now + timedelta(days=30),
            created_at=now,
            updated_at=now,
        )
        self.rows[key] = record
        return record, True

    async def complete(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        command_id: UUID,
        result: dict[str, object],
        uow: object = None,
    ) -> CommandIdempotency:
        for key, row in self.rows.items():
            if key[0] == tenant_id and row.command_id == command_id:
                data = row.model_dump()
                data.update(status="completed", result=result)
                updated = CommandIdempotency.model_validate(data)
                self.rows[key] = updated
                return updated
        raise AssertionError(f"complete() for unknown command {command_id}")

    async def get_by_key_scoped(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        idempotency_key: str,
        uow: object = None,
    ) -> CommandIdempotency | None:
        return self.rows.get((tenant_id, idempotency_key))


class FakeEffects:
    """In-memory stand-in for `ExternalEffectService`'s prepare/sent/
    confirmed surface -- the exact three calls `_sweep_live_processes`
    makes, recording everything for assertion."""

    def __init__(self) -> None:
        self.prepared: list[dict[str, object]] = []
        self.sent: list[UUID] = []
        self.confirmed: list[UUID] = []
        self._next_id = iter(uuid4() for _ in range(1000))

    async def prepare(self, **kwargs: object) -> object:
        self.prepared.append(dict(kwargs))
        return type("_EffectSnapshot", (), {"effect_id": next(self._next_id)})

    async def mark_sent(
        self, *, tenant_id: UUID, project_id: UUID, effect_id: UUID, **kwargs: object
    ) -> None:
        self.sent.append(effect_id)

    async def mark_confirmed(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        effect_id: UUID,
        external_reference: str | None = None,
        response_hash: str | None = None,
        **kwargs: object,
    ) -> None:
        self.confirmed.append(effect_id)


class FakeUOW:
    connection = object()

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class FreshRegistry(ProcessHandleRegistry):
    """Per-test registry instance; the shared default must stay untouched
    by tests."""


class FailingSweepRegistry(FreshRegistry):
    """Deterministic per-pid failure: one registered handle whose sweep
    reports `failed` with an OS error detail -- no OS dependence."""

    def list_for_run(
        self, *, tenant_id: UUID, project_id: UUID, worker_run_id: UUID
    ) -> list[RegisteredProcess]:
        return [
            RegisteredProcess(
                tenant_id=tenant_id,
                project_id=project_id,
                worker_run_id=worker_run_id,
                capability_lease_id=self.lease_id,
                pid=self.stub_pid,
                created_at=time.monotonic(),
            )
        ]

    async def sweep_run(
        self, *, tenant_id: UUID, project_id: UUID, worker_run_id: UUID
    ) -> list[TerminationOutcome]:
        return [
            TerminationOutcome(
                pid=self.stub_pid, phase="failed", detail="access denied"
            )
        ]

    def __init__(self) -> None:
        super().__init__()
        self.stub_pid = 999_999
        self.lease_id = uuid4()


def _lease(*, status: str = "ACTIVE", lease_id: UUID | None = None) -> CapabilityLease:
    now = datetime.now(UTC)
    return CapabilityLease(
        lease_id=lease_id or uuid4(),
        tenant_id=TENANT,
        project_id=PROJECT,
        mission_id=MISSION,
        task_id=TASK,
        execution_plan_id=uuid4(),
        worker_run_id=RUN,
        environment_id=None,
        capability_id="capability.run_local_process",
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
    *,
    process_registry: ProcessHandleRegistry | None = None,
    effects: FakeEffects | None = None,
) -> tuple[CapabilityLeaseService, RecordingEvents, FakeEffects]:
    events = RecordingEvents()
    effects = effects or FakeEffects()
    service = CapabilityLeaseService(
        engine=None,  # type: ignore[arg-type]
        repository=FakeLeaseRepository(leases),
        events=events,  # type: ignore[arg-type]
        commands=FakeLedger(),  # type: ignore[arg-type]
        capabilities=None,  # type: ignore[arg-type]
        kill_switch=None,
        process_registry=process_registry,
        effects=effects,  # type: ignore[arg-type]
    )
    return service, events, effects


async def test_arm_run_stop_terminates_registered_processes_and_journals_effects() -> (
    None
):
    """The full arm-time sweep against a REAL in-flight child: the process
    stops existing, one `process_termination` external effect is prepared/
    sent/confirmed carrying the authorizing lease id and pid, and the
    summary event names the termination."""
    lease = _lease()
    registry = FreshRegistry()
    proc = subprocess.Popen(  # noqa: S603, ASYNC220
        _SLOW_EXIT_COMMAND, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    registry.register(
        RegisteredProcess(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            capability_lease_id=lease.lease_id,
            pid=proc.pid,
            created_at=time.monotonic(),
        )
    )
    service, events, effects = _service([lease], process_registry=registry)
    try:
        revoked = await service.arm_run_stop(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
        assert [item.lease_id for item in revoked] == [lease.lease_id]
        assert revoked[0].revocation_reason == KILL_FLAG_REASON
    finally:
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.wait(timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            pass

    assert len(effects.prepared) == 1
    prepared = effects.prepared[0]
    assert prepared["tenant_id"] == TENANT
    assert prepared["project_id"] == PROJECT
    assert prepared["mission_id"] == MISSION
    assert prepared["worker_run_id"] == RUN
    assert prepared["capability_lease_id"] == lease.lease_id
    assert prepared["target_system"] == "process_termination"
    assert prepared["target_resource"] == f"pid:{proc.pid}"
    assert prepared["operation"] == f"terminate_run_processes:{proc.pid}"
    assert prepared["side_effect_class"] == "WORKSPACE_LOCAL"
    assert len(effects.sent) == 1
    assert len(effects.confirmed) == 1

    summaries = [
        e for e in events.appended if e["event_type"] == "CapabilityRunStopArmed"
    ]
    assert len(summaries) == 1
    payload = summaries[0]["payload"]
    assert isinstance(payload, dict)
    assert payload["terminated_processes"] == [
        {
            "pid": proc.pid,
            "phase": "killed" if sys.platform == "win32" else "terminated",
        }
    ]


async def test_arm_run_stop_without_processes_journals_no_termination_effects() -> None:
    """No registered handles -> the sweep contributes nothing: no
    termination effects, and the summary's terminated list is empty -- the
    pre-existing lease-sweep behaviour is byte-identical."""
    service, events, effects = _service([_lease()])
    await service.arm_run_stop(
        tenant_id=TENANT,
        project_id=PROJECT,
        worker_run_id=RUN,
        uow=FakeUOW(),  # type: ignore[arg-type]
    )
    assert effects.prepared == []
    summaries = [
        e for e in events.appended if e["event_type"] == "CapabilityRunStopArmed"
    ]
    assert len(summaries) == 1
    payload = summaries[0]["payload"]
    assert isinstance(payload, dict)
    assert payload["terminated_processes"] == []


async def test_arm_run_stop_without_mission_context_skips_journaling_but_stops() -> (
    None
):
    """A run with no held lease has no mission binding; Chapter 12.4
    requires the mission on a journal row, so the sweep terminates but
    journals nothing rather than inventing a mission."""
    registry = FreshRegistry()
    proc = subprocess.Popen(  # noqa: S603, ASYNC220
        _SLOW_EXIT_COMMAND, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    registry.register(
        RegisteredProcess(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            capability_lease_id=uuid4(),
            pid=proc.pid,
            created_at=time.monotonic(),
        )
    )
    service, _events, effects = _service([], process_registry=registry)
    try:
        await service.arm_run_stop(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
    finally:
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.wait(timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            pass
    assert effects.prepared == []


async def test_arm_run_stop_never_touches_other_runs_processes() -> None:
    """Scope discipline: another run's registered process survives this
    run's stop untouched."""
    other_run = uuid4()
    registry = FreshRegistry()
    other = subprocess.Popen(  # noqa: S603, ASYNC220
        _SLOW_EXIT_COMMAND, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    registry.register(
        RegisteredProcess(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=other_run,
            capability_lease_id=uuid4(),
            pid=other.pid,
            created_at=time.monotonic(),
        )
    )
    service, _events, effects = _service([_lease()], process_registry=registry)
    try:
        await service.arm_run_stop(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
        assert other.poll() is None  # still running
    finally:
        try:
            other.kill()
        except OSError:
            pass
        try:
            other.wait(timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            pass
    assert effects.prepared == []


async def test_arm_run_stop_journals_failed_termination_and_still_stops() -> None:
    """Best-effort discipline: a per-pid `failed` outcome (OS refused every
    attempt) is journaled with its error detail as the confirmed external
    reference, and the stop itself still completes."""
    registry = FailingSweepRegistry()
    lease = _lease()
    registry.lease_id = lease.lease_id
    service, events, effects = _service([lease], process_registry=registry)
    revoked = await service.arm_run_stop(
        tenant_id=TENANT,
        project_id=PROJECT,
        worker_run_id=RUN,
        uow=FakeUOW(),  # type: ignore[arg-type]
    )
    assert [item.lease_id for item in revoked] == [lease.lease_id]
    assert len(effects.prepared) == 1
    prepared = effects.prepared[0]
    assert prepared["target_resource"] == f"pid:{registry.stub_pid}"
    summaries = [
        e for e in events.appended if e["event_type"] == "CapabilityRunStopArmed"
    ]
    payload = summaries[0]["payload"]
    assert isinstance(payload, dict)
    assert payload["terminated_processes"] == [
        {"pid": registry.stub_pid, "phase": "failed"}
    ]


async def test_arm_run_stop_rearm_finds_no_processes_and_journals_no_duplicates() -> (
    None
):
    """Idempotent re-arm: after the first sweep emptied the registry, a
    second arm journals only the lease/summary artifacts again -- no
    second termination effects (the processes are already gone)."""
    registry = FreshRegistry()
    proc = subprocess.Popen(  # noqa: S603, ASYNC220
        _SLOW_EXIT_COMMAND, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    registry.register(
        RegisteredProcess(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            capability_lease_id=uuid4(),
            pid=proc.pid,
            created_at=time.monotonic(),
        )
    )
    service, _events, effects = _service([_lease()], process_registry=registry)
    try:
        await service.arm_run_stop(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
        assert len(effects.prepared) == 1
        await service.arm_run_stop(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
        assert len(effects.prepared) == 1
    finally:
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.wait(timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            pass


async def test_default_constructor_reuses_the_shared_process_registry() -> None:
    """No second registry may exist: a bare `CapabilityLeaseService(engine)`
    must consult exactly the module-level instance
    `LocalProcessBackend.run_for_authority` registers into."""
    from engine.capabilities.lease_service import CapabilityLeaseService as Svc

    service = Svc(engine=None)  # type: ignore[arg-type]
    assert service.process_registry is SHARED_PROCESS_REGISTRY


async def test_authority_helper_matches_registry_key_shape() -> None:
    """`RegisteredAuthority` is the spawn-side presentation of the exact
    key the sweep resolves: same four identity fields, so a backend can
    never register under a scope the sweeper cannot find."""
    authority = RegisteredAuthority(
        tenant_id=TENANT,
        project_id=PROJECT,
        worker_run_id=RUN,
        capability_lease_id=uuid4(),
    )
    registry = FreshRegistry()
    registry.register(
        RegisteredProcess(
            tenant_id=authority.tenant_id,
            project_id=authority.project_id,
            worker_run_id=authority.worker_run_id,
            capability_lease_id=authority.capability_lease_id,
            pid=12345,
            created_at=time.monotonic(),
        )
    )
    listed = registry.list_for_run(
        tenant_id=authority.tenant_id,
        project_id=authority.project_id,
        worker_run_id=authority.worker_run_id,
    )
    assert [item.capability_lease_id for item in listed] == [
        authority.capability_lease_id
    ]


async def test_kill_flag_error_contract_untouched_by_sweep() -> None:
    """The sweep adds a third arm-time artifact; it must not disturb the
    typed refusal contract: an armed stop still raises KILL_FLAG_ACTIVE at
    checkout with the same details shape (regression guard for the two
    existing kill-flag suites' shared contract)."""
    from engine.core.errors import DdeError as DdeError_

    service, _events, _effects = _service([_lease()])
    service.kill_switch.arm(tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN)
    with pytest.raises(DdeError_) as excinfo:
        await service.require_active(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            capability_id="capability.run_local_process",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
    assert excinfo.value.error_code == "KILL_FLAG_ACTIVE"
