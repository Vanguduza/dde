"""Shared PostgreSQL fixtures for `engine.execution`/`engine.environments`/
`engine.workspaces` tests (Chapter 19.1).

Builds on `tests.support.routing_fixtures.build_routing_fixture` (a real,
APPROVED TaskGraph plus a compiled `ContextPackage`) and adds a real,
persisted `RouteDecision` (`engine.routing.service.RouterService`) — the
same "already-materialised upstream object" pattern
`tests/support/routing_fixtures.py` itself uses for `Task`/`ContextPackage`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.context_package import ContextPackage
from engine.contracts.mission import Mission
from engine.contracts.route_decision import RouteDecision
from engine.contracts.task import Task
from engine.routing.service import RouterService
from tests.support.db import TenantFixture
from tests.support.routing_fixtures import build_routing_fixture


@dataclass
class ExecutionFixture:
    tenant: TenantFixture
    mission: Mission
    task: Task
    context_package: ContextPackage
    route_decision: RouteDecision


async def build_execution_fixture(
    engine: AsyncEngine,
    root: Path,
    *,
    mission_slug: str,
    task_class: str = "implementation",
    risk_class: str = "low",
    estimated_effort_override: str | None = None,
) -> ExecutionFixture:
    routing_fixture = await build_routing_fixture(
        engine,
        root,
        mission_slug=mission_slug,
        task_class=task_class,
        risk_class=risk_class,
    )
    task = routing_fixture.task
    if estimated_effort_override is not None:
        task = task.model_copy(update={"estimated_effort": estimated_effort_override})
    router = RouterService(engine)
    route_decision = await router.route(task=task)
    return ExecutionFixture(
        tenant=routing_fixture.tenant,
        mission=routing_fixture.mission,
        task=task,
        context_package=routing_fixture.context_package,
        route_decision=route_decision,
    )
