"""Shared PostgreSQL fixtures for `engine.routing` tests (Chapter 19.1).

Builds a real, APPROVED two-node TaskGraph: the task under test (whose
`task_class`/`risk_class`/`requires_approval` vary per call) plus a
trivial verification task connected by a `verifies` edge — satisfying
Chapter 4.2's "every leaf path terminates in a `verifies` edge" invariant
the same way every other task in this codebase's fixtures does, since a
single-node, edge-less graph only validates when its lone node is itself
`task_class = verification` (as `tests/support/context_fixtures.py` uses).
This lets routing tests exercise real `implementation`/`verification`
task classes without weakening `engine.planning.validate.validate_graph`.

Also compiles a real `ContextPackage` for the task under test through
`engine.context.service.ContextService`, matching Chapter 2.5's spine
ordering (ContextPackage precedes RouteDecision) and proving the router
runs against genuine, already-persisted cross-module state — not a mock.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.context.model import ContextBudgetExceeded
from engine.context.service import ContextService
from engine.contracts.context_package import ContextPackage
from engine.contracts.mission import Mission
from engine.contracts.task import Task
from engine.contracts.task_graph_edge import TaskGraphEdge
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.missions.service import MissionService
from engine.planning.planner import PLANNER_POLICY_VERSION
from engine.truth.service import TruthService
from tests.support.context_fixtures import build_fake_repo
from tests.support.db import TenantFixture, seed_tenant

REQUIREMENT_SLUG = "REQ-ROUTE-1"


@dataclass
class RoutingFixture:
    tenant: TenantFixture
    mission: Mission
    task: Task
    verification_task: Task
    context_package: ContextPackage


async def build_routing_fixture(
    engine: AsyncEngine,
    root: Path,
    *,
    mission_slug: str,
    task_class: str = "implementation",
    risk_class: str = "low",
    blast_radius: str = "local",
    requires_approval: bool = False,
    mission_title: str = "Routing fixture mission",
    mission_intent: str = "Exercise the deterministic router end to end",
    requirement_slug: str = REQUIREMENT_SLUG,
    requirement_statement: str = (
        "Routing fixture tasks route to a real worker profile"
    ),
) -> RoutingFixture:
    build_fake_repo(root)
    tenant = await seed_tenant(engine)
    truth = TruthService(engine)
    requirement = await truth.draft_requirement(
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        slug=requirement_slug,
        statement=requirement_statement,
        constraints=[],
        acceptance_conditions=["A RouteDecision persists with real gate outcomes"],
    )
    await truth.approve_requirement(
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        requirement_id=requirement.requirement_id,
    )

    mission_service = MissionService(engine, EventService(engine))
    mission = await mission_service.create_mission(
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        slug=mission_slug,
        title=mission_title,
        intent=mission_intent,
        success_definition="A RouteDecision persists with real gate outcomes",
        scope=["engine", "tests"],
        requirement_refs=[requirement_slug],
        autonomy_ceiling=3,
    )

    now = datetime.now(UTC)
    graph_id = uuid7()
    task_id = uuid7()
    verification_task_id = uuid7()
    task = Task(
        task_id=task_id,
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        mission_id=mission.mission_id,
        graph_id=graph_id,
        title="Task under test",
        intent="Implement the routing fixture behaviour",
        task_class=task_class,
        requirement_refs=[requirement_slug],
        feature_refs=[],
        success_criteria=["Behaviour is implemented"],
        expected_write_scope=["engine/routing"],
        expected_read_scope=["engine/routing", "AGENTS.md"],
        blast_radius=blast_radius,
        risk_class=risk_class,
        estimated_effort="s",
        autonomy_ceiling=2,
        requires_approval=requires_approval,
        verification_profile_ref="unit",
        status="CREATED",
        lock_version=1,
        created_at=now,
        updated_at=now,
    )
    verification_task = Task(
        task_id=verification_task_id,
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        mission_id=mission.mission_id,
        graph_id=graph_id,
        title="Verify task under test",
        intent="Verify the routing fixture behaviour",
        task_class="verification",
        requirement_refs=[requirement_slug],
        feature_refs=[],
        success_criteria=["Behaviour is verified"],
        expected_write_scope=["tests/unit"],
        expected_read_scope=["engine/routing"],
        blast_radius="local",
        risk_class="low",
        estimated_effort="xs",
        autonomy_ceiling=2,
        requires_approval=False,
        verification_profile_ref="unit",
        status="CREATED",
        lock_version=1,
        created_at=now,
        updated_at=now,
    )
    edge = TaskGraphEdge(
        edge_id=uuid7(),
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        mission_id=mission.mission_id,
        graph_id=graph_id,
        from_task_id=task_id,
        to_task_id=verification_task_id,
        edge_type="verifies",
        contract_ref=None,
        created_at=now,
        updated_at=now,
    )
    graph = await mission_service.create_task_graph(
        mission=mission,
        graph_id=graph_id,
        tasks=[task, verification_task],
        edges=[edge],
        planning_mode="template",
        planner_policy_version=PLANNER_POLICY_VERSION,
        rationale="DDE-009 routing fixture",
        created_by_principal=tenant.principal_id,
        approved_requirement_slugs={requirement_slug},
    )
    assert graph.status == "APPROVED", graph
    persisted_tasks = await mission_service.list_tasks_for_graph(
        tenant_id=tenant.tenant_id, project_id=tenant.project_id, graph_id=graph_id
    )
    by_id = {item.task_id: item for item in persisted_tasks}
    persisted_task = by_id[task_id]

    context_service = ContextService(engine, root=root)
    compiled = await context_service.compile(task=persisted_task)
    assert not isinstance(compiled, ContextBudgetExceeded), compiled

    return RoutingFixture(
        tenant=tenant,
        mission=mission,
        task=persisted_task,
        verification_task=by_id[verification_task_id],
        context_package=compiled,
    )
