"""`engine.recovery` durability (Chapter 19.1): a fresh session/engine
reads back the exact committed `ExternalEffect` the writing process
produced around a real `WorkerManagerService.invoke_run`."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from engine.capabilities.lease_service import CapabilityLeaseService
from engine.context.repo import repo_root
from engine.recovery.service import ExternalEffectService
from engine.workers.adapter import WorkerAction
from engine.workers.registry import WorkerProfileRegistry
from engine.workers.scripted_adapter import ScriptedWorkerAdapter
from engine.workers.service import WorkerManagerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.worker_fixtures import build_worker_fixture


@pytest.mark.asyncio
async def test_second_session_sees_the_exact_committed_effect_row(
    tmp_path: Path,
) -> None:
    root = repo_root()
    writer_engine = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            writer_engine, tmp_path, mission_slug="MISSION-EFFECT-RECOVERY"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(writer_engine, root=root)
        leases = CapabilityLeaseService(writer_engine)
        registry = WorkerProfileRegistry()
        await registry.register_profile(ScriptedWorkerAdapter(workspaces, leases))
        manager = WorkerManagerService(writer_engine, registry, leases=leases)
        run = await manager.invoke_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=WorkerAction(
                command=[sys.executable, "-c", "print('dde-effect-recovery')"]
            ),
            idempotency_key="effect-recovery-invoke-1",
        )
        written = await workspaces.effects.list_for_run(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            worker_run_id=run.run_id,
        )
        assert len(written) == 1
        assert written[0].status == "CONFIRMED"
        committed = written[0]
    finally:
        await writer_engine.dispose()

    reader_engine = new_engine()
    try:
        reader = ExternalEffectService(reader_engine)
        reloaded = await reader.get_effect(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            effect_id=committed.effect_id,
        )
        assert reloaded == committed
        listed = await reader.list_for_run(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            worker_run_id=run.run_id,
        )
        assert listed == [committed]
    finally:
        if workspace is not None:
            await WorkspaceService(reader_engine, root=root).cleanup(
                workspace=workspace
            )
        await reader_engine.dispose()
