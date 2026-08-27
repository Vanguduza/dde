"""DDE-061 chaos suite — fault injection at production call sites.

Not a second copy of `tests/recovery`. Each scenario attempts a real
schedule, kill, or environment replacement through WorkerManager /
ExecutionEnvironmentService / ExecutionPlanService.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from engine.capabilities.lease_service import CapabilityLeaseService
from engine.context.repo import repo_root
from engine.core.errors import DdeError
from engine.environments.service import ExecutionEnvironmentService
from engine.execution.service import ExecutionPlanService
from engine.missions.attempts import TaskAttemptService
from engine.workers.adapter import WorkerAction
from engine.workers.registry import WorkerProfileRegistry
from engine.workers.scripted_adapter import ScriptedWorkerAdapter
from engine.workers.service import WorkerManagerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.worker_fixtures import build_worker_fixture

_PASS = WorkerAction(command=[sys.executable, "-c", "pass"])
_KILL = WorkerAction(command=[sys.executable, "-c", "raise SystemExit(1)"])


async def _manager(engine, workspaces: WorkspaceService) -> WorkerManagerService:
    leases = CapabilityLeaseService(engine)
    registry = WorkerProfileRegistry()
    await registry.register_profile(ScriptedWorkerAdapter(workspaces, leases))
    return WorkerManagerService(engine, registry, leases=leases)


@pytest.mark.asyncio
async def test_chaos_invoke_run_refuses_draining_and_failed_environments(
    tmp_path: Path,
) -> None:
    """Ch.7.3/7.4: no run is scheduled into DRAINING or FAILED — attempted
    at `WorkerManagerService.invoke_run`, not `assert_schedulable` alone."""
    root = repo_root()
    engine = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-CHAOS-NOT-SCHEDULABLE"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(engine, root=root)
        manager = await _manager(engine, workspaces)
        environments = ExecutionEnvironmentService(engine)
        original = await environments.get_environment(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            environment_id=fixture.execution_plan.execution_environment_id,
        )
        draining = await environments.transition(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            environment_id=original.environment_id,
            target_lifecycle_state="DRAINING",
            lock_version=original.lock_version,
        )
        with pytest.raises(DdeError) as drain_exc:
            await manager.invoke_run(
                task=fixture.task,
                execution_plan=fixture.execution_plan,
                workspace=fixture.workspace,
                input_context_hash=fixture.context_package.assembly_hash,
                action=_PASS,
                idempotency_key="chaos-drain-1",
            )
        assert drain_exc.value.error_code == "ENVIRONMENT_FAILED"
        failed = await environments.transition(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            environment_id=draining.environment_id,
            target_lifecycle_state="FAILED",
            lock_version=draining.lock_version,
        )
        with pytest.raises(DdeError) as failed_exc:
            await manager.invoke_run(
                task=fixture.task,
                execution_plan=fixture.execution_plan,
                workspace=fixture.workspace,
                input_context_hash=fixture.context_package.assembly_hash,
                action=_PASS,
                idempotency_key="chaos-failed-1",
            )
        assert failed_exc.value.error_code == "ENVIRONMENT_FAILED"
        assert failed.lifecycle_state == "FAILED"
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=root).cleanup(workspace=workspace)
        await engine.dispose()


@pytest.mark.asyncio
async def test_chaos_replacement_mid_run_same_attempt_new_environment(
    tmp_path: Path,
) -> None:
    """Ch.19.1 Environment replacement mid-run: replace() then resume_run
    on the same TaskAttempt with a workspace bound to the substitute."""
    root = repo_root()
    engine = new_engine()
    workspace = None
    replacement_workspace = None
    try:
        fixture = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-CHAOS-REPLACE-ENV"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(engine, root=root)
        manager = await _manager(engine, workspaces)
        first = await manager.invoke_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=_KILL,
            idempotency_key="chaos-replace-1",
        )
        assert first.status == "FAILED"
        attempt = await TaskAttemptService(engine).get_attempt(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            attempt_id=first.task_attempt_id,
        )
        assert attempt.status == "IN_PROGRESS"
        environments = ExecutionEnvironmentService(engine)
        original = await environments.get_environment(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            environment_id=fixture.execution_plan.execution_environment_id,
        )
        replaced = await environments.replace(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            environment_id=original.environment_id,
            lock_version=original.lock_version,
        )
        assert replaced.retired.lifecycle_state == "REPLACEMENT"
        replacement_workspace = await ExecutionPlanService(engine).provision_workspace(
            plan=fixture.execution_plan,
            task=fixture.task,
            base_revision=fixture.workspace.base_revision,
            execution_environment_id=replaced.replacement.environment.environment_id,
        )
        resumed = await manager.resume_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=replacement_workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=_PASS,
            attempt_id=first.task_attempt_id,
            idempotency_key="chaos-replace-2",
        )
        assert resumed.task_attempt_id == first.task_attempt_id
        assert resumed.sequence == 2
        assert resumed.status == "COMPLETED"
        assert resumed.environment_id == replaced.replacement.environment.environment_id
        assert resumed.environment_id != first.environment_id
        assert fixture.mission.status != "FAILED"
    finally:
        if replacement_workspace is not None:
            await WorkspaceService(engine, root=root).cleanup(
                workspace=replacement_workspace
            )
        if workspace is not None:
            await WorkspaceService(engine, root=root).cleanup(workspace=workspace)
        await engine.dispose()


@pytest.mark.asyncio
async def test_chaos_killed_worker_replaced_without_mission_loss(
    tmp_path: Path,
) -> None:
    """S3 residue: a killed worker is replaced without mission loss, as a
    new WorkerRun on the surviving attempt."""
    root = repo_root()
    engine = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-CHAOS-KILL-WORKER"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(engine, root=root)
        manager = await _manager(engine, workspaces)
        first = await manager.invoke_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=_KILL,
            idempotency_key="chaos-kill-1",
        )
        assert first.status == "FAILED"
        assert first.failure_class == "WORKER_COMMAND_FAILED"
        attempt = await TaskAttemptService(engine).get_attempt(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            attempt_id=first.task_attempt_id,
        )
        assert attempt.status == "IN_PROGRESS"
        with pytest.raises(DdeError) as bypass:
            await manager.invoke_run(
                task=fixture.task,
                execution_plan=fixture.execution_plan,
                workspace=fixture.workspace,
                input_context_hash=fixture.context_package.assembly_hash,
                action=_PASS,
                idempotency_key="chaos-kill-bypass",
            )
        assert bypass.value.error_code == "POLICY_DENIED"
        resumed = await manager.resume_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=_PASS,
            attempt_id=first.task_attempt_id,
            idempotency_key="chaos-kill-2",
        )
        assert resumed.task_attempt_id == first.task_attempt_id
        assert resumed.sequence == 2
        assert resumed.status == "COMPLETED"
        assert resumed.mission_id == fixture.mission.mission_id
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=root).cleanup(workspace=workspace)
        await engine.dispose()


@pytest.mark.asyncio
async def test_chaos_core_restart_then_resume_replaces_killed_worker(
    tmp_path: Path,
) -> None:
    """Worker crash plus a new engine (Core gone) still resumes the same
    attempt. Not a second copy of tests/recovery row re-reads: the mutation
    is resume_run after process replacement."""
    root = repo_root()
    writer = new_engine()
    workspace = None
    reader = None
    try:
        fixture = await build_worker_fixture(
            writer, tmp_path, mission_slug="MISSION-CHAOS-CORE-RESTART"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(writer, root=root)
        manager = await _manager(writer, workspaces)
        first = await manager.invoke_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=_KILL,
            idempotency_key="chaos-core-1",
        )
        assert first.status == "FAILED"
        await writer.dispose()
        writer = None
        reader = new_engine()
        reader_workspaces = WorkspaceService(reader, root=root)
        resumed_manager = await _manager(reader, reader_workspaces)
        resumed = await resumed_manager.resume_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=_PASS,
            attempt_id=first.task_attempt_id,
            idempotency_key="chaos-core-2",
        )
        assert resumed.task_attempt_id == first.task_attempt_id
        assert resumed.sequence == 2
        assert resumed.status == "COMPLETED"
        attempt = await TaskAttemptService(reader).get_attempt(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            attempt_id=first.task_attempt_id,
        )
        assert attempt.status == "IN_PROGRESS"
        assert attempt.checkpoint_id is not None
    finally:
        engine = reader or writer
        if engine is not None and workspace is not None:
            await WorkspaceService(engine, root=root).cleanup(workspace=workspace)
        if writer is not None:
            await writer.dispose()
        if reader is not None:
            await reader.dispose()
