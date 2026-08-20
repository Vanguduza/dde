"""Chapter 19.1 recovery: a killed Core (new engine/session) reconstructs
from the committed checkpoint plus durable attempt results.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from engine.capabilities.lease_service import CapabilityLeaseService
from engine.context.repo import repo_root
from engine.recovery.checkpoint_service import CheckpointService
from engine.recovery.replay import ReplayService
from engine.workers.adapter import WorkerAction
from engine.workers.registry import WorkerProfileRegistry
from engine.workers.scripted_adapter import ScriptedWorkerAdapter
from engine.workers.service import WorkerManagerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.worker_fixtures import build_worker_fixture


@pytest.mark.asyncio
async def test_second_session_resumes_from_committed_checkpoint(
    tmp_path: Path,
) -> None:
    writer = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            writer, tmp_path, mission_slug="MISSION-CKPT-RECOVERY"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(writer, root=repo_root())
        leases = CapabilityLeaseService(writer)
        registry = WorkerProfileRegistry()
        await registry.register_profile(ScriptedWorkerAdapter(workspaces, leases))
        manager = WorkerManagerService(writer, registry, leases=leases)
        run = await manager.invoke_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=WorkerAction(
                command=[sys.executable, "-c", "print('core-restart')"]
            ),
            idempotency_key="ckpt-recovery-1",
        )
        assert run.checkpoint_id is not None
        checkpoint_id = run.checkpoint_id
        tenant_id = fixture.tenant.tenant_id
        project_id = fixture.tenant.project_id
        mission_id = fixture.mission.mission_id
        task_id = fixture.task.task_id
    finally:
        await writer.dispose()

    reader = new_engine()
    try:
        loaded = await CheckpointService(reader).get_checkpoint(
            tenant_id=tenant_id,
            project_id=project_id,
            checkpoint_id=checkpoint_id,
        )
        assert loaded.checkpoint_id == checkpoint_id
        assert loaded.task_id == task_id
        plan = await ReplayService(reader).plan_for_mission(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
        )
        assert plan.checkpoint is not None
        assert plan.checkpoint.checkpoint_id == checkpoint_id
        assert plan.next_action == "verify"
    finally:
        if workspace is not None:
            await WorkspaceService(reader, root=repo_root()).cleanup(
                workspace=workspace
            )
        await reader.dispose()
