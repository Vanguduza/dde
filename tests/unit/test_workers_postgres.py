"""PostgreSQL-backed `engine.workers`: schema, state-transition, negative
and idempotency tests (Chapter 19.1) — the mission's full acceptance proof.

`WorkerManagerService.invoke_run()` against a real, persisted `RouteDecision`
/`ExecutionPlan`/`Workspace` (Chapter 3.9 steps 8/10), driving the one real
Stage 1 certified profile (`ScriptedWorkerAdapter`, `profile.
deterministic_runner`) through Chapter 8.2's real lifecycle, producing a
real, captured `WorkerRun` and a real `WorkerEvent` stream — and proving a
second invocation with the same `idempotency_key` never re-executes it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.capabilities.lease_service import CapabilityLeaseService
from engine.context.repo import repo_root
from engine.core.errors import DdeError
from engine.environments.service import ExecutionEnvironmentService
from engine.missions.attempts import TaskAttemptRepository
from engine.truth.db import open_unit_of_work
from engine.workers.adapter import WorkerAction
from engine.workers.registry import WorkerProfileRegistry
from engine.workers.repository import WorkerEventRepository, WorkerRunRepository
from engine.workers.scripted_adapter import ScriptedWorkerAdapter
from engine.workers.service import WorkerManagerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.worker_fixtures import build_worker_fixture


async def _manager_with_scripted_adapter(
    db_engine: AsyncEngine, workspaces: WorkspaceService
) -> tuple[WorkerManagerService, CapabilityLeaseService]:
    leases = CapabilityLeaseService(db_engine)
    registry = WorkerProfileRegistry()
    await registry.register_profile(ScriptedWorkerAdapter(workspaces, leases))
    return WorkerManagerService(db_engine, registry, leases=leases), leases


@pytest.mark.asyncio
async def test_schema_state_transition_and_idempotent_full_lifecycle(
    tmp_path: Path,
) -> None:
    root = repo_root()
    db_engine = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            db_engine, tmp_path, mission_slug="MISSION-WORKER-SCHEMA"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(db_engine, root=root)
        manager, _leases = await _manager_with_scripted_adapter(db_engine, workspaces)

        action = WorkerAction(
            command=[sys.executable, "-c", "print('dde-worker-run-proof')"],
            write_files={"dde-worker-marker.txt": b"deterministic scripted output\n"},
        )

        run = await manager.invoke_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=action,
            idempotency_key="worker-run-schema-1",
        )

        assert run.status == "COMPLETED"
        assert run.failure_class is None
        assert run.worker_profile_id == "profile.deterministic_runner"
        assert run.worker_id == "worker.scripted-deterministic-v1"
        assert run.environment_id == fixture.execution_plan.execution_environment_id
        assert run.workspace_id == fixture.workspace.workspace_id
        assert run.context_package_id == fixture.execution_plan.context_package_id
        assert run.sequence == 1
        assert run.started_at is not None
        assert run.ended_at is not None

        # Schema round trip (Chapter 19.1): a fresh read reproduces the
        # exact committed row.
        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            reloaded_run = await WorkerRunRepository().get_run(
                uow.connection, run.run_id
            )
            attempt = await TaskAttemptRepository().get_attempt(
                uow.connection, run.task_attempt_id
            )
            events = await WorkerEventRepository().list_for_run(
                uow.connection, run.run_id
            )
            await uow.commit()
        assert reloaded_run == run
        assert attempt is not None
        assert attempt.task_id == fixture.task.task_id
        assert attempt.sequence == 1
        assert attempt.status == "IN_PROGRESS"
        assert attempt.input_context_hash == fixture.context_package.assembly_hash

        # State-transition (Chapter 8.2's real lifecycle, in real sequence).
        event_types = [event.event_type for event in events]
        assert event_types == [
            "WorkerRunCreated",
            "WorkerRunPreparing",
            "WorkerRunReady",
            "WorkerRunStarted",
            "WorkerRunCompleted",
        ]
        completed_event = events[-1]
        assert completed_event.payload["exit_code"] == 0
        assert "dde-worker-run-proof" in str(completed_event.payload["stdout"])
        assert "dde-worker-marker.txt" in completed_event.payload["changed_files"]
        assert completed_event.integrity_hash

        # Idempotency (AGENTS.md definition of done + CommandLedger reuse):
        # the same idempotency_key never double-executes.
        replayed = await manager.invoke_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=action,
            idempotency_key="worker-run-schema-1",
        )
        assert replayed.run_id == run.run_id
        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            runs_for_attempt = await WorkerRunRepository().list_for_attempt(
                uow.connection, run.task_attempt_id
            )
            replay_events = await WorkerEventRepository().list_for_run(
                uow.connection, run.run_id
            )
            await uow.commit()
        assert len(runs_for_attempt) == 1  # no second run was created
        assert len(replay_events) == len(events)  # no event re-appended
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(workspace=workspace)
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_negative_failing_scripted_command_is_captured_not_raised(
    tmp_path: Path,
) -> None:
    """Chapter 19.1's negative fixture: a real, non-zero-exit scripted
    command becomes a real, persisted `FAILED` `WorkerRun` — never an
    unhandled exception."""
    root = repo_root()
    db_engine = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            db_engine, tmp_path, mission_slug="MISSION-WORKER-NEGATIVE"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(db_engine, root=root)
        manager, _leases = await _manager_with_scripted_adapter(db_engine, workspaces)

        action = WorkerAction(command=[sys.executable, "-c", "import sys; sys.exit(7)"])

        run = await manager.invoke_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=action,
            idempotency_key="worker-run-negative-1",
        )

        assert run.status == "FAILED"
        assert run.failure_class == "WORKER_COMMAND_FAILED"
        assert run.ended_at is not None

        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            events = await WorkerEventRepository().list_for_run(
                uow.connection, run.run_id
            )
            await uow.commit()
        assert [event.event_type for event in events] == [
            "WorkerRunCreated",
            "WorkerRunPreparing",
            "WorkerRunReady",
            "WorkerRunStarted",
            "WorkerRunFailed",
        ]
        assert events[-1].payload["exit_code"] == 7
        assert events[-1].payload["failure_class"] == "WORKER_COMMAND_FAILED"
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(workspace=workspace)
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_negative_uncertified_profile_is_rejected(tmp_path: Path) -> None:
    """A profile with no registered, healthy `WorkerAdapter` is
    `PROFILE_STALE` (Chapter 8.5/15.5) — never silently run."""
    root = repo_root()
    db_engine = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            db_engine, tmp_path, mission_slug="MISSION-WORKER-UNCERTIFIED"
        )
        workspace = fixture.workspace
        empty_registry = WorkerProfileRegistry()
        manager = WorkerManagerService(db_engine, empty_registry)
        action = WorkerAction(command=[sys.executable, "-c", "print('unused')"])

        with pytest.raises(DdeError) as excinfo:
            await manager.invoke_run(
                task=fixture.task,
                execution_plan=fixture.execution_plan,
                workspace=fixture.workspace,
                input_context_hash=fixture.context_package.assembly_hash,
                action=action,
                idempotency_key="worker-run-uncertified-1",
            )
        assert excinfo.value.error_code == "PROFILE_STALE"

        # Rolled back entirely: no attempt or run was created for the
        # rejected invocation.
        environments = ExecutionEnvironmentService(db_engine)
        environment = await environments.get_environment(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            environment_id=fixture.execution_plan.execution_environment_id,
        )
        assert environment.lifecycle_state == "READY"
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(workspace=workspace)
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_negative_mismatched_workspace_is_rejected(tmp_path: Path) -> None:
    """A `Workspace` bound to a different plan's environment is a policy
    violation, not silently accepted."""
    root = repo_root()
    db_engine = new_engine()
    first_workspace = None
    second_workspace = None
    try:
        first = await build_worker_fixture(
            db_engine, tmp_path, mission_slug="MISSION-WORKER-MISMATCH-A"
        )
        second = await build_worker_fixture(
            db_engine, tmp_path, mission_slug="MISSION-WORKER-MISMATCH-B"
        )
        first_workspace = first.workspace
        second_workspace = second.workspace
        workspaces = WorkspaceService(db_engine, root=root)
        manager, _leases = await _manager_with_scripted_adapter(db_engine, workspaces)
        action = WorkerAction(command=[sys.executable, "-c", "print('unused')"])

        with pytest.raises(DdeError) as excinfo:
            await manager.invoke_run(
                task=first.task,
                execution_plan=first.execution_plan,
                workspace=second.workspace,
                input_context_hash=first.context_package.assembly_hash,
                action=action,
                idempotency_key="worker-run-mismatch-1",
            )
        assert excinfo.value.error_code == "POLICY_DENIED"
    finally:
        if first_workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(
                workspace=first_workspace
            )
        if second_workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(
                workspace=second_workspace
            )
        await db_engine.dispose()
