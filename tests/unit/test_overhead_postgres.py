"""PostgreSQL proof that Chapter 16.4 overhead is written at the real
WorkerRunStarted production call site (`WorkerManagerService.invoke_run`).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from engine.capabilities.lease_service import CapabilityLeaseService
from engine.context.repo import repo_root
from engine.overhead.formula import overhead_tokens
from engine.overhead.repository import ControlPlaneOverheadRepository
from engine.truth.db import open_unit_of_work
from engine.workers.adapter import WorkerAction
from engine.workers.registry import WorkerProfileRegistry
from engine.workers.scripted_adapter import ScriptedWorkerAdapter
from engine.workers.service import WorkerManagerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.worker_fixtures import build_worker_fixture


@pytest.mark.asyncio
async def test_invoke_run_persists_full_overhead_formula(tmp_path: Path) -> None:
    root = repo_root()
    db_engine = new_engine()
    try:
        fixture = await build_worker_fixture(
            db_engine, tmp_path, mission_slug="MISSION-OVERHEAD-FORMULA"
        )
        workspaces = WorkspaceService(db_engine, root=root)
        leases = CapabilityLeaseService(db_engine)
        registry = WorkerProfileRegistry()
        await registry.register_profile(ScriptedWorkerAdapter(workspaces, leases))
        manager = WorkerManagerService(db_engine, registry, leases=leases)

        run = await manager.invoke_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=WorkerAction(
                command=[sys.executable, "-c", "print('overhead-proof')"]
            ),
            idempotency_key="overhead-formula-run-1",
        )
        assert run.status == "COMPLETED"

        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            row = await ControlPlaneOverheadRepository().get_by_worker_run_id(
                uow.connection, run.run_id
            )
            await uow.commit()

        assert row is not None
        assert row.worker_run_id == run.run_id
        assert row.context_assembly_tokens == fixture.context_package.assembly_tokens
        assert row.routing_tokens == 0
        assert row.route_critic_tokens == 0
        assert row.route_critic_invoked is False
        assert row.judge_tokens == 0
        assert row.workload_class
        assert row.overhead_tokens == overhead_tokens(
            context_assembly=row.context_assembly_tokens,
            context_critic=row.context_critic_tokens,
            routing=row.routing_tokens,
            route_critic=row.route_critic_tokens,
            planning=row.planning_tokens,
            judge=row.judge_tokens,
        )
    finally:
        await db_engine.dispose()
