"""Shared PostgreSQL fixtures for `engine.workers` tests (Chapter 19.1).

Builds on `tests.support.execution_fixtures.build_execution_fixture` (a
real, persisted `Task`/`ContextPackage`/`RouteDecision`) and adds a real,
persisted `ExecutionPlan` plus a real, provisioned `Workspace` — the exact
"given a RouteDecision + ExecutionPlan + provisioned environment/workspace"
starting point the DDE-011 mission brief names.

`task_class="verification"` is used deliberately: Chapter 6.2's declared
routing policy (`engine.routing.policy.WORKLOAD_CLASSES["verification"]`)
prefers `profile.deterministic_runner`, the one profile this mission
certifies — so the real router genuinely selects the one real certified
profile Stage 1 has, rather than a test needing to override routing's own
decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.context_package import ContextPackage
from engine.contracts.execution_plan import ExecutionPlan
from engine.contracts.mission import Mission
from engine.contracts.route_decision import RouteDecision
from engine.contracts.task import Task
from engine.contracts.workspace import Workspace
from engine.execution.service import ExecutionPlanService
from tests.support.capability_fixtures import ensure_capabilities_seeded
from tests.support.db import TenantFixture
from tests.support.execution_fixtures import build_execution_fixture


@dataclass
class WorkerFixture:
    tenant: TenantFixture
    mission: Mission
    task: Task
    context_package: ContextPackage
    route_decision: RouteDecision
    execution_plan: ExecutionPlan
    workspace: Workspace


async def build_worker_fixture(
    engine: AsyncEngine,
    root: Path,
    *,
    mission_slug: str,
) -> WorkerFixture:
    execution_fixture = await build_execution_fixture(
        engine, root, mission_slug=mission_slug, task_class="verification"
    )
    await ensure_capabilities_seeded(
        engine,
        tenant_id=execution_fixture.tenant.tenant_id,
        project_id=execution_fixture.tenant.project_id,
    )
    plan_service = ExecutionPlanService(engine)
    plan = await plan_service.plan(
        task=execution_fixture.task,
        route_decision=execution_fixture.route_decision,
        context_package_id=execution_fixture.context_package.package_id,
    )
    assert plan.worker_profile_id == "profile.deterministic_runner", plan
    workspace = await plan_service.provision_workspace(
        plan=plan, task=execution_fixture.task, base_revision="HEAD"
    )
    return WorkerFixture(
        tenant=execution_fixture.tenant,
        mission=execution_fixture.mission,
        task=execution_fixture.task,
        context_package=execution_fixture.context_package,
        route_decision=execution_fixture.route_decision,
        execution_plan=plan,
        workspace=workspace,
    )
