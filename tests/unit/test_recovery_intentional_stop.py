"""PostgreSQL-backed EDR-0010/EDR-0012 tests (accepted 2026-08-23).

Production call sites under test:
- `RecoveryService.classify_run_stop_failure_class` -- resolves a run's
  stop-record state to its durable failure class (ARMED ->
  INTENTIONALLY_STOPPED, else the borrowed legacy AUTHORIZATION_FAILURE);
- `RecoveryService.assert_clear_to_retry` -- refuses any new WorkerRun for
  a task whose latest run holds an ARMED durable stop record, before the
  matrix is even consulted (Chapter 12.4: an intentional stop is never
  blind-retried; only verified absence permits a new mutation);
- `WorkerManagerService._drive_lifecycle` -- consults the classifier when
  adapter-start raises KILL_FLAG_ACTIVE and durably records the mid-run
  kill as INTENTIONALLY_STOPPED, never the borrowed
  WORKER_CAPABILITY_DENIED class (EDR-0012 Finding A);
- `WorkerManagerService.resume_run` -- refuses with typed KILL_FLAG_ACTIVE
  while any run of the task holds an ARMED stop record, BEFORE any new
  WorkerRun insert, lease grant or prior-run replace (EDR-0012 Finding B).
"""

import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import text

from engine.capabilities.kill_switch import (
    KILL_FLAG_REASON,
    record_run_stop,
)
from engine.capabilities.lease_service import CapabilityLeaseService
from engine.context.repo import repo_root
from engine.contracts.worker_run import WorkerRun
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.idempotency import CommandLedger
from engine.events.repository import EventsRepository
from engine.missions.attempts import TaskAttemptService
from engine.recovery.dispatch import RecoveryService
from engine.truth.db import open_unit_of_work
from engine.workers.adapter import RunHandle, WorkerAction
from engine.workers.registry import WorkerProfileRegistry
from engine.workers.repository import WorkerRunRepository
from engine.workers.scripted_adapter import ScriptedWorkerAdapter
from engine.workers.service import WorkerManagerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.worker_fixtures import build_worker_fixture


async def _seed_environment(engine, fixture) -> object:
    """One minimal execution_environments row; worker_runs.environment_id
    carries a real FK to it."""
    now = datetime.now(UTC)
    environment = {
        "environment_id": uuid7(),
        "tenant_id": fixture.tenant.tenant_id,
        "project_id": fixture.tenant.project_id,
        "class": "shared",
        "type": "local_process",
        "os_family": sys.platform,
        "architecture": platform.machine(),
        "runtime_image": "test-image",
        "image_digest": "sha256:test",
        "toolchain_manifest": "{}",
        "toolchain_manifest_hash": "test",
        "resource_limits": "{}",
        "network_policy": "{}",
        "filesystem_policy": "{}",
        "isolation_level": "none",
        "credential_profile_id": None,
        "security_profile_id": None,
        "capability_compatibility": "{}",
        "worker_compatibility": "{}",
        "status": "ACTIVE",
        "health_status": "HEALTHY",
        "lifecycle_state": "ACTIVE",
        "lock_version": 1,
        "created_at": now,
        "updated_at": now,
    }
    columns = ", ".join(environment)
    params = ", ".join(f":{name}" for name in environment)
    statement = text(
        f"INSERT INTO execution_environments ({columns}) VALUES ({params})"  # noqa: S608  code-owned column names, bound values
    )
    async with engine.begin() as connection:
        await connection.execute(statement, environment)
    return environment["environment_id"]


async def _attempt_and_run(fixture, engine) -> tuple[object, object]:
    attempts = TaskAttemptService(engine)
    attempt = await attempts.create(
        task=fixture.task,
        execution_plan=fixture.execution_plan,
        workspace_revision="deadbeef",
        input_context_hash=fixture.context_package.assembly_hash,
    )
    environment_id = await _seed_environment(engine, fixture)
    now = datetime.now(UTC)
    plan_id = fixture.execution_plan.plan_id
    run = {
        "run_id": uuid7(),
        "tenant_id": fixture.tenant.tenant_id,
        "project_id": fixture.tenant.project_id,
        "mission_id": fixture.mission.mission_id,
        "task_attempt_id": attempt.attempt_id,
        "sequence": 1,
        "execution_plan_id": plan_id,
        "worker_id": "worker-test",
        "worker_profile_id": fixture.execution_plan.worker_profile_id,
        "environment_id": environment_id,
        "workspace_id": fixture.workspace.workspace_id,
        "context_package_id": fixture.context_package.package_id,
        "policy_version": "test",
        "lease_set_hash": "test",
        "status": "FAILED",
        "failure_class": None,
        "created_at": now,
        "updated_at": now,
    }
    columns = ", ".join(run)
    params = ", ".join(f":{name}" for name in run)
    statement = text(
        f"INSERT INTO worker_runs ({columns}) VALUES ({params})"  # noqa: S608
    )
    async with engine.begin() as connection:
        await connection.execute(statement, run)
    return attempt, run


@pytest.mark.asyncio
async def test_armed_stop_classifies_intentionally_stopped(tmp_path) -> None:
    """A run whose durable stop record is ARMED classifies as
    INTENTIONALLY_STOPPED; a run with no stop record keeps the borrowed
    legacy AUTHORIZATION_FAILURE meaning."""
    engine = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-EDR10-A"
        )
        workspace = fixture.workspace
        _attempt, run = await _attempt_and_run(fixture, engine)
        service = RecoveryService(engine)

        legacy = await service.classify_run_stop_failure_class(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            worker_run_id=run["run_id"],
        )
        assert legacy == "AUTHORIZATION_FAILURE"

        await record_run_stop(
            CommandLedger(engine),
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            worker_run_id=run["run_id"],
            armed=True,
            reason=KILL_FLAG_REASON,
            uow=None,
        )

        stopped = await service.classify_run_stop_failure_class(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            worker_run_id=run["run_id"],
        )
        assert stopped == "INTENTIONALLY_STOPPED"
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_armed_stop_refuses_new_worker_run_until_disarmed(tmp_path) -> None:
    """assert_clear_to_retry refuses while ARMED (KILL_FLAG_ACTIVE), and a
    DISARMED record -- the operator's acknowledgement flip -- lets the
    guarded path proceed again."""
    engine = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-EDR10-B"
        )
        workspace = fixture.workspace
        attempt, run = await _attempt_and_run(fixture, engine)
        ledger = CommandLedger(engine)
        service = RecoveryService(engine)
        kwargs = {
            "tenant_id": fixture.tenant.tenant_id,
            "project_id": fixture.tenant.project_id,
            "task_id": fixture.task.task_id,
            "mission_id": fixture.mission.mission_id,
        }

        await record_run_stop(
            ledger,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            worker_run_id=run["run_id"],
            armed=True,
            reason=KILL_FLAG_REASON,
            uow=None,
        )
        with pytest.raises(DdeError) as captured:
            await service.assert_clear_to_retry(**kwargs)
        assert captured.value.error_code == "KILL_FLAG_ACTIVE"
        assert captured.value.details is not None
        assert captured.value.details["failure_class"] == "INTENTIONALLY_STOPPED"
        assert captured.value.details["action"] == "acknowledge_stop"

        await TaskAttemptService(engine).fail(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            attempt_id=attempt.attempt_id,
            failure_class="INTENTIONALLY_STOPPED",
            checkpoint_id=None,
        )

        await record_run_stop(
            ledger,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            worker_run_id=run["run_id"],
            armed=False,
            reason="operator acknowledged",
            uow=None,
        )
        retry_of = await service.assert_clear_to_retry(**kwargs)
        assert retry_of == attempt.attempt_id
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


async def _registry(
    leases: CapabilityLeaseService, workspaces: WorkspaceService
) -> WorkerProfileRegistry:
    """The certified scripted profile bound to the SAME `CapabilityLeaseService`
    the test's operator surface uses, so arm/disarm state is one coherent
    authority in the process."""
    registry = WorkerProfileRegistry()
    await registry.register_profile(ScriptedWorkerAdapter(workspaces, leases))
    return registry


class _ArmOnStartAdapter(ScriptedWorkerAdapter):
    """Test double: arms the run's stop at `start()` entry -- the run row
    exists and is RUNNING, but no require_active checkout has happened yet.
    The typed KILL_FLAG_ACTIVE refusal then reaches `_drive_lifecycle`'s
    exception mapping exactly as a real checkout refusal would
    (`require_active` raises this same error code from inside
    `ScriptedWorkerAdapter.start`).

    The durable half of the stop is written here through the same ledger
    machinery `CapabilityLeaseService.arm_run_stop` uses, so recovery's
    consult sees it from any process/connection."""

    def __init__(
        self,
        workspaces: WorkspaceService,
        leases: CapabilityLeaseService,
        commands: CommandLedger,
        tenant_id: UUID,
        project_id: UUID,
    ) -> None:
        super().__init__(workspaces, leases)
        self._commands = commands
        self._tenant_id = tenant_id
        self._project_id = project_id

    async def prepare(self, **kwargs):  # type: ignore[no-untyped-def]
        return await super().prepare(**kwargs)  # type: ignore[arg-type]

    async def start(self, worker_run: WorkerRun) -> RunHandle:
        await record_run_stop(
            self._commands,
            tenant_id=self._tenant_id,
            project_id=self._project_id,
            worker_run_id=worker_run.run_id,
            armed=True,
            reason=KILL_FLAG_REASON,
            uow=None,
        )
        raise DdeError(
            "KILL_FLAG_ACTIVE",
            "Kill flag is armed for this worker run -- capability checkout refused",
            details={
                "worker_run_id": str(worker_run.run_id),
                "reason": KILL_FLAG_REASON,
            },
        )


@pytest.mark.asyncio
async def test_mid_run_kill_refusal_records_intentionally_stopped(
    tmp_path: Path,
) -> None:
    """EDR-0012 Finding A: a run killed mid-flight by an armed stop -- its
    adapter-start checkout raises KILL_FLAG_ACTIVE after the run is already
    RUNNING -- is durably recorded as INTENTIONALLY_STOPPED on BOTH the
    WorkerRun and the TaskAttempt. The borrowed WORKER_CAPABILITY_DENIED
    (-> AUTHORIZATION_FAILURE) class must never absorb an operator's
    intentional stop."""
    engine = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-EDR12-MIDRUN"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(engine, root=repo_root())
        leases = CapabilityLeaseService(engine)
        ledger = CommandLedger(engine)
        armed_adapter = _ArmOnStartAdapter(
            workspaces,
            leases,
            commands=ledger,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        )
        registry = WorkerProfileRegistry()
        await registry.register_profile(armed_adapter)
        manager = WorkerManagerService(engine, registry, leases=leases)

        action = WorkerAction(
            command=[sys.executable, "-c", "print('never runs')"],
            write_files={"src/killed.py": b"x = 1\n"},
        )
        # The lifecycle does NOT re-raise the refusal: it lands a terminal
        # FAILED run and returns it. What this test pins is the durable
        # classification that writer records before returning.
        killed = await manager.invoke_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=action,
            idempotency_key="edr12-midrun-1",
        )
        assert killed.status == "FAILED"
        assert killed.failure_class == "INTENTIONALLY_STOPPED"

        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            killed = await WorkerRunRepository().list_for_mission(
                uow.connection, fixture.mission.mission_id
            )
        assert len(killed) == 1
        assert killed[0].status == "FAILED"
        assert killed[0].failure_class == "INTENTIONALLY_STOPPED"

        attempts = await TaskAttemptService(engine).list_for_task(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            task_id=fixture.task.task_id,
        )
        assert attempts[-1].status == "FAILED"
        assert attempts[-1].failure_class == "INTENTIONALLY_STOPPED"

        # The stop record is durably ARMED for the killed run (written by
        # the adapter hook through the same ledger machinery), so recovery
        # refuses any new WorkerRun for this task outright.
        recovery = RecoveryService(engine)
        with pytest.raises(DdeError) as clear:
            await recovery.assert_clear_to_retry(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                task_id=fixture.task.task_id,
                mission_id=fixture.mission.mission_id,
            )
        assert clear.value.error_code == "KILL_FLAG_ACTIVE"
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_resume_run_refused_while_stop_armed_before_any_new_run(
    tmp_path: Path,
) -> None:
    """EDR-0012 Finding B: with an ARMED durable stop on run R1 whose
    attempt is still IN_PROGRESS (R1 not yet terminal), resume_run must
    refuse with typed KILL_FLAG_ACTIVE BEFORE any new WorkerRun insert,
    lease grant or prior-run replace. The negative proof: no worker_runs
    row beyond R1 exists after the refused call."""
    engine = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-EDR12-RESUME-BLOCK"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(engine, root=repo_root())
        leases = CapabilityLeaseService(engine)
        manager = WorkerManagerService(
            engine, await _registry(leases, workspaces), leases=leases
        )

        attempt = await TaskAttemptService(engine).create(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace_revision="deadbeef",
            input_context_hash=fixture.context_package.assembly_hash,
        )

        # R1: a non-terminal predecessor run of this attempt -- exactly the
        # shape a stop armed mid-flight leaves behind.
        environment_id = await _seed_environment(engine, fixture)
        now = datetime.now(UTC)
        r1 = {
            "run_id": uuid7(),
            "tenant_id": fixture.tenant.tenant_id,
            "project_id": fixture.tenant.project_id,
            "mission_id": fixture.mission.mission_id,
            "task_attempt_id": attempt.attempt_id,
            "sequence": 1,
            "execution_plan_id": fixture.execution_plan.plan_id,
            "worker_id": "worker-test",
            "worker_profile_id": fixture.execution_plan.worker_profile_id,
            "environment_id": environment_id,
            "workspace_id": fixture.workspace.workspace_id,
            "context_package_id": fixture.context_package.package_id,
            "policy_version": "test",
            "lease_set_hash": "test",
            "status": "RUNNING",
            "failure_class": None,
            "created_at": now,
            "updated_at": now,
        }
        columns = ", ".join(r1)
        params = ", ".join(f":{name}" for name in r1)
        statement = text(f"INSERT INTO worker_runs ({columns}) VALUES ({params})")  # noqa: S608  code-owned column names, bound values
        async with engine.begin() as connection:
            await connection.execute(statement, r1)

        # The operator arms the stop on R1 while its attempt stays
        # IN_PROGRESS and R1 has not gone terminal -- through the same
        # production service surface (registry flag + durable ledger row in
        # one transaction).
        await leases.arm_run_stop(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            worker_run_id=r1["run_id"],
        )

        action = WorkerAction(command=[sys.executable, "-c", "print('x')"])
        kwargs = {
            "task": fixture.task,
            "execution_plan": fixture.execution_plan,
            "workspace": fixture.workspace,
            "input_context_hash": fixture.context_package.assembly_hash,
            "action": action,
            "attempt_id": attempt.attempt_id,
            "idempotency_key": "edr12-resume-blocked-1",
        }
        with pytest.raises(DdeError) as refused:
            await manager.resume_run(**kwargs)  # type: ignore[arg-type]
        assert refused.value.error_code == "KILL_FLAG_ACTIVE"

        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            runs = await WorkerRunRepository().list_for_attempt(
                uow.connection, attempt.attempt_id
            )
        assert [item.run_id for item in runs] == [
            r1["run_id"]
        ]  # no new WorkerRun was minted past the stop
        assert runs[0].status == "RUNNING"  # predecessor not silently replaced

        # The refusal is observable in the event store, consistent with the
        # existing _record_resume_refusal trail.
        events = await _recent_event_types(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            attempt_id=attempt.attempt_id,
        )
        assert "ResumeRefused" in events

        # After disarm (the operator acknowledgement through the service
        # layer, which drops the in-memory flag AND flips the durable row),
        # resume proceeds exactly once as today: new run on the SAME
        # attempt, terminal.
        await leases.disarm_run_stop(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            worker_run_id=r1["run_id"],
            reason="operator acknowledged",
        )
        resumed = await manager.resume_run(**kwargs)  # type: ignore[arg-type]
        assert resumed.status == "COMPLETED"
        assert resumed.task_attempt_id == attempt.attempt_id
        assert resumed.sequence == 2
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


async def _recent_event_types(
    engine, *, tenant_id: UUID, project_id: UUID, attempt_id: UUID
) -> list[str]:
    async with open_unit_of_work(
        engine, tenant_id=tenant_id, project_id=project_id
    ) as uow:
        rows = await EventsRepository().list_events_for_aggregate(
            uow.connection, "task_attempt", attempt_id
        )
        await uow.commit()
    return [row.event_type for row in rows]
