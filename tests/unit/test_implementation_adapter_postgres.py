"""PostgreSQL-backed second adapter (DDE-025).

`LocalImplementationAdapter` is a real `WorkerAdapter` behind
`profile.longcontext_economy`. Bulk-implementation routing already selects
that profile; this suite proves invoke_run can drive it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from engine.capabilities.lease_service import CapabilityLeaseService
from engine.context.repo import repo_root
from engine.execution.service import ExecutionPlanService
from engine.workers.adapter import WorkerAction
from engine.workers.implementation_adapter import (
    IMPLEMENTATION_WORKER_ID,
    LocalImplementationAdapter,
)
from engine.workers.registry import WorkerProfileRegistry
from engine.workers.service import WorkerManagerService
from engine.workspaces.service import WorkspaceService
from tests.support.capability_fixtures import ensure_capabilities_seeded
from tests.support.db import new_engine
from tests.support.execution_fixtures import build_execution_fixture


@pytest.mark.asyncio
async def test_local_implementation_adapter_completes_an_invoke_run(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    workspace = None
    try:
        fixture = await build_execution_fixture(
            engine, tmp_path, mission_slug="MISSION-WORKER-IMPLEMENTATION"
        )
        await ensure_capabilities_seeded(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        )
        plan_service = ExecutionPlanService(engine)
        plan = await plan_service.plan(
            task=fixture.task,
            route_decision=fixture.route_decision,
            context_package_id=fixture.context_package.package_id,
        )
        assert plan.worker_profile_id == "profile.longcontext_economy"
        workspace = await plan_service.provision_workspace(
            plan=plan, task=fixture.task, base_revision="HEAD"
        )
        workspaces = WorkspaceService(engine, root=repo_root())
        leases = CapabilityLeaseService(engine)
        registry = WorkerProfileRegistry()
        await registry.register_profile(LocalImplementationAdapter(workspaces, leases))
        manager = WorkerManagerService(engine, registry, leases=leases)
        run = await manager.invoke_run(
            task=fixture.task,
            execution_plan=plan,
            workspace=workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=WorkerAction(command=[sys.executable, "-c", "print('impl')"]),
            idempotency_key="implementation-adapter-1",
        )
        assert run.status == "COMPLETED"
        assert run.worker_profile_id == "profile.longcontext_economy"
        assert run.worker_id == IMPLEMENTATION_WORKER_ID
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()
