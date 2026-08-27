"""PostgreSQL-backed Chapter 12.1/12.2/12.5/12.6 (DDE-023).

Production call sites: WorkerManagerService.invoke_run records the
checkpoint and commits/fails the attempt; VerificationRunnerService.run
finalises COMPLETED; ReplayService.assert_clear_to_start_attempt and
TaskAttemptService.create refuse re-running completed work; do_not_repeat
is the logical mutation token, not the caller key.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from engine.capabilities.lease_service import CapabilityLeaseService
from engine.context.repo import repo_root
from engine.core.errors import DdeError
from engine.missions.attempts import ATTEMPT_COMPLETED, TaskAttemptService
from engine.recovery.checkpoint_service import CheckpointService
from engine.recovery.replay import (
    EVENT_WINDOW_EXPIRED,
    MUTATION_ALREADY_DONE,
    WORKER_EVENT_HOT_WINDOW,
    ReplayService,
)
from engine.recovery.workflow import MissionWorkflowService
from engine.workers.adapter import WorkerAction
from engine.workers.registry import WorkerProfileRegistry
from engine.workers.scripted_adapter import ScriptedWorkerAdapter
from engine.workers.service import WorkerManagerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.worker_fixtures import build_worker_fixture


class _FrozenClock:
    def __init__(self, instant: datetime) -> None:
        self._instant = instant

    def now(self) -> datetime:
        return self._instant


async def _manager(engine, workspaces: WorkspaceService) -> WorkerManagerService:
    leases = CapabilityLeaseService(engine)
    registry = WorkerProfileRegistry()
    await registry.register_profile(ScriptedWorkerAdapter(workspaces, leases))
    return WorkerManagerService(engine, registry, leases=leases)


@pytest.mark.asyncio
async def test_invoke_run_records_checkpoint_and_refuses_completed_rerun(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-CKPT-COMPLETE"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(engine, root=repo_root())
        manager = await _manager(engine, workspaces)
        action = WorkerAction(command=[sys.executable, "-c", "print('ckpt')"])
        run = await manager.invoke_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=action,
            idempotency_key="ckpt-complete-1",
        )
        assert run.status == "COMPLETED"
        assert run.checkpoint_id is not None
        checkpoint = await CheckpointService(engine).get_checkpoint(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            checkpoint_id=run.checkpoint_id,
        )
        assert checkpoint.task_id == fixture.task.task_id
        assert str(fixture.task.task_id) in checkpoint.completed_work
        assert checkpoint.next_action == "verify"
        assert CheckpointService(engine).is_valid(checkpoint)
        assert checkpoint.do_not_repeat  # confirmed run_local_process

        with pytest.raises(DdeError) as excinfo:
            await manager.invoke_run(
                task=fixture.task,
                execution_plan=fixture.execution_plan,
                workspace=fixture.workspace,
                input_context_hash=fixture.context_package.assembly_hash,
                action=action,
                idempotency_key="ckpt-complete-2",
            )
        assert excinfo.value.error_code == MUTATION_ALREADY_DONE
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_completed_attempt_is_not_replayed_as_new_attempt(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-CKPT-SIBLING"
        )
        workspace = fixture.workspace
        attempts = TaskAttemptService(engine)
        first = await attempts.create(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace_revision="deadbeef",
            input_context_hash=fixture.context_package.assembly_hash,
        )
        await attempts.finalize(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            attempt_id=first.attempt_id,
            verification_refs=[],
        )
        with pytest.raises(DdeError) as excinfo:
            await attempts.create(
                task=fixture.task,
                execution_plan=fixture.execution_plan,
                workspace_revision="deadbeef",
                input_context_hash=fixture.context_package.assembly_hash,
            )
        assert excinfo.value.error_code == ATTEMPT_COMPLETED
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_replay_skips_completed_and_surfaces_event_window_expired(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-CKPT-REPLAY"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(engine, root=repo_root())
        manager = await _manager(engine, workspaces)
        run = await manager.invoke_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=WorkerAction(command=[sys.executable, "-c", "pass"]),
            idempotency_key="ckpt-replay-1",
        )
        attempts = TaskAttemptService(engine)
        await attempts.finalize(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            attempt_id=run.task_attempt_id,
            verification_refs=[],
        )
        replay = ReplayService(engine)
        plan = await replay.plan_for_mission(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.mission.mission_id,
        )
        assert fixture.task.task_id in plan.skip_task_ids
        assert plan.checkpoint is not None
        assert plan.event_window_expired is False

        stale = ReplayService(
            engine,
            clock=_FrozenClock(
                datetime.now(UTC) + WORKER_EVENT_HOT_WINDOW + timedelta(days=1)
            ),
        )
        expired_plan = await stale.plan_for_mission(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.mission.mission_id,
        )
        assert expired_plan.event_window_expired is True
        assert expired_plan.reconstruction_source == "checkpoint_and_attempts"
        assert expired_plan.checkpoint is not None
        with pytest.raises(DdeError) as excinfo:
            expired_plan.require_events()
        assert excinfo.value.error_code == EVENT_WINDOW_EXPIRED
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_resume_run_reuses_attempt_and_generic_retry_is_refused(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-CKPT-RESUME"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(engine, root=repo_root())
        manager = await _manager(engine, workspaces)
        action = WorkerAction(
            command=[sys.executable, "-c", "raise SystemExit(1)"],
        )
        first = await manager.invoke_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=action,
            idempotency_key="ckpt-resume-1",
        )
        assert first.status == "FAILED"
        attempt = await TaskAttemptService(engine).get_attempt(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            attempt_id=first.task_attempt_id,
        )
        assert attempt.status == "IN_PROGRESS"

        # Chapter 3.9: the attempt survives a recoverable worker crash.
        # invoke_run must not mint a second attempt; resume_run replaces.
        workflow = MissionWorkflowService(engine)
        with pytest.raises(DdeError) as generic:
            await workflow.retry(policy={})
        assert generic.value.error_code == "POLICY_DENIED"
        allowed = await workflow.retry(policy={"failure_class": "WORKER_FAILURE"})
        assert allowed.allow_new_worker_run is True
        with pytest.raises(DdeError) as denied:
            await workflow.retry(policy={"failure_class": "AUTHORIZATION_FAILURE"})
        assert denied.value.error_code == "POLICY_DENIED"
        with pytest.raises(DdeError):
            await workflow.wait(condition="approval")
        recorded = await workflow.request_approval(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.mission.mission_id,
            approval_type="architecture_change",
            requested_by=fixture.tenant.principal_id,
            idempotency_key="ckpt-approval-1",
            reason="authorization failure",
        )
        assert recorded.status == "REQUESTED"
        routed = await workflow.reroute(reason="worker untrusted")
        assert routed.action == "reroute"

        with pytest.raises(DdeError) as second_attempt:
            await manager.invoke_run(
                task=fixture.task,
                execution_plan=fixture.execution_plan,
                workspace=fixture.workspace,
                input_context_hash=fixture.context_package.assembly_hash,
                action=WorkerAction(command=[sys.executable, "-c", "pass"]),
                idempotency_key="ckpt-resume-2",
            )
        assert second_attempt.value.error_code == "POLICY_DENIED"
        retry = await manager.resume_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=WorkerAction(command=[sys.executable, "-c", "pass"]),
            attempt_id=first.task_attempt_id,
            idempotency_key="ckpt-resume-2b",
        )
        assert retry.task_attempt_id == first.task_attempt_id
        assert retry.sequence == 2
        assert retry.status == "COMPLETED"
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_resume_run_adds_a_new_run_on_the_same_attempt(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-CKPT-RESUME-RUN"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(engine, root=repo_root())
        manager = await _manager(engine, workspaces)
        created = await TaskAttemptService(engine).create(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace_revision="deadbeef",
            input_context_hash=fixture.context_package.assembly_hash,
        )
        resumed = await manager.resume_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=WorkerAction(command=[sys.executable, "-c", "pass"]),
            attempt_id=created.attempt_id,
            idempotency_key="ckpt-resume-run-1",
        )
        assert resumed.task_attempt_id == created.attempt_id
        assert resumed.sequence == 1
        assert resumed.status == "COMPLETED"
        with pytest.raises(DdeError) as excinfo:
            await manager.resume_run(
                task=fixture.task,
                execution_plan=fixture.execution_plan,
                workspace=fixture.workspace,
                input_context_hash=fixture.context_package.assembly_hash,
                action=WorkerAction(command=[sys.executable, "-c", "pass"]),
                attempt_id=created.attempt_id,
                idempotency_key="ckpt-resume-run-2",
            )
        assert excinfo.value.error_code == MUTATION_ALREADY_DONE
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()
