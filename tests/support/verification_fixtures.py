"""Shared PostgreSQL fixtures for `engine.verification` tests (Chapter
19.1).

Builds on `tests.support.worker_fixtures.build_worker_fixture` (a real,
COMPLETED `WorkerRun` in a real, provisioned `Workspace`) -- the exact
"given a completed WorkerRun + its Workspace" starting point DDE-012's
mission brief names.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.capabilities.lease_service import CapabilityLeaseService
from engine.contracts.context_package import ContextPackage
from engine.contracts.execution_plan import ExecutionPlan
from engine.contracts.mission import Mission
from engine.contracts.task import Task
from engine.contracts.worker_run import WorkerRun
from engine.contracts.workspace import Workspace
from engine.workers.adapter import WorkerAction
from engine.workers.registry import WorkerProfileRegistry
from engine.workers.scripted_adapter import ScriptedWorkerAdapter
from engine.workers.service import WorkerManagerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import TenantFixture
from tests.support.worker_fixtures import build_worker_fixture


@dataclass
class VerificationFixture:
    tenant: TenantFixture
    mission: Mission
    task: Task
    context_package: ContextPackage
    execution_plan: ExecutionPlan
    workspace: Workspace
    worker_run: WorkerRun


async def build_verification_fixture(
    engine: AsyncEngine,
    root: Path,
    *,
    mission_slug: str,
) -> VerificationFixture:
    """A real, `COMPLETED` `WorkerRun` (Chapter 8.2) whose workspace is
    untouched by any check yet -- the test itself writes whatever real
    files a given `CheckSpec` needs before invoking the runner, exactly as
    a real worker's diff would have landed them."""
    worker_fixture = await build_worker_fixture(engine, root, mission_slug=mission_slug)
    workspaces = WorkspaceService(engine, root=root)
    leases = CapabilityLeaseService(engine)
    registry = WorkerProfileRegistry()
    await registry.register_profile(ScriptedWorkerAdapter(workspaces, leases))
    manager = WorkerManagerService(engine, registry, leases=leases)
    action = WorkerAction(
        command=[sys.executable, "-c", "print('dde-verification-fixture-worker')"]
    )
    run = await manager.invoke_run(
        task=worker_fixture.task,
        execution_plan=worker_fixture.execution_plan,
        workspace=worker_fixture.workspace,
        input_context_hash=worker_fixture.context_package.assembly_hash,
        action=action,
        idempotency_key=f"{mission_slug}-verification-fixture-worker-run",
    )
    assert run.status == "COMPLETED", run
    return VerificationFixture(
        tenant=worker_fixture.tenant,
        mission=worker_fixture.mission,
        task=worker_fixture.task,
        context_package=worker_fixture.context_package,
        execution_plan=worker_fixture.execution_plan,
        workspace=worker_fixture.workspace,
        worker_run=run,
    )
