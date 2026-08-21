"""PostgreSQL-backed Chapter 5.10 knowledge graph (Chapter 19.1). Exercises
`engine.knowledge.service.KnowledgeGraphService`, the production writer of
`asserted_edges`/`derived_edges`, against a real database -- and the real
`engine.missions.service.MissionService.create_task_graph` call site that
asserts `task_to_requirement` edges when a TaskGraph reaches `APPROVED`.
"""

from __future__ import annotations

import pytest

from engine.core.clock import SystemClock
from engine.core.ids import uuid7
from engine.events.repository import EventsRepository
from engine.events.service import EventService
from engine.knowledge.repository import AssertedEdgeRepository, DerivedEdgeRepository
from engine.knowledge.service import KnowledgeGraphService
from engine.missions.service import MissionService
from engine.planning.hashing import graph_hash
from engine.planning.planner import PLANNER_POLICY_VERSION
from engine.planning.service import TaskGraphService
from engine.planning.templates import add_endpoint_template
from engine.truth.db import open_unit_of_work
from tests.support.db import new_engine, seed_tenant

REQUIREMENT_SLUG = "REQ-HEALTH"


async def _create_mission(service: MissionService, fixture, *, slug: str):
    return await service.create_mission(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        slug=slug,
        title="Health endpoint",
        intent="Add a /health endpoint",
        success_definition="healthz returns ok",
        scope=["engine", "schemas", "tests"],
        requirement_refs=[REQUIREMENT_SLUG],
        autonomy_ceiling=3,
    )


@pytest.mark.asyncio
async def test_assert_edge_is_idempotent_on_identity() -> None:
    """Chapter 5.10, AGENTS.md idempotency rule: re-asserting the same
    `(project_id, edge_type, source_key, target_key)` returns the
    existing row rather than duplicating it."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = KnowledgeGraphService(engine)

        first = await service.assert_edge(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edge_type="requirement_to_edr",
            source_key="requirement:REQ-1",
            target_key="edr:EDR-1",
            asserted_by_mechanism="test",
        )
        second = await service.assert_edge(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edge_type="requirement_to_edr",
            source_key="requirement:REQ-1",
            target_key="edr:EDR-1",
            asserted_by_mechanism="test",
        )

        assert first.edge_id == second.edge_id

        async with open_unit_of_work(
            engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            edges = await AssertedEdgeRepository().list_for_project(
                uow.connection, fixture.project_id
            )
            await uow.commit()
        assert len(edges) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_retract_edge_moves_status_without_physical_delete() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = KnowledgeGraphService(engine)

        edge = await service.assert_edge(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edge_type="decision_to_consequence",
            source_key="decision:D-1",
            target_key="consequence:C-1",
            asserted_by_mechanism="test",
        )

        await service.retract_edge(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edge_id=edge.edge_id,
        )

        async with open_unit_of_work(
            engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            edges = await AssertedEdgeRepository().list_for_project(
                uow.connection, fixture.project_id
            )
            await uow.commit()
        assert len(edges) == 1
        assert edges[0].status == "retracted"
        assert edges[0].retracted_at is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_recompute_derived_edges_replaces_prior_generation_and_reports_fresh(
    tmp_path,
) -> None:
    """Chapter 5.10: a recompute replaces the whole prior generation for
    the project (never a mix of two commits' derived edges), and reports
    `stale_share == 0.0` immediately after -- every row's
    `derived_from_commit` is the commit that was just read."""
    (tmp_path / "engine").mkdir()
    (tmp_path / "engine" / "widget.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("deadbeef\n", encoding="utf-8")

    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = KnowledgeGraphService(engine, root=tmp_path)

        first_pass = await service.recompute_derived_edges(
            tenant_id=fixture.tenant_id, project_id=fixture.project_id
        )
        assert first_pass.total_count >= 1
        assert first_pass.stale_share == 0.0

        async with open_unit_of_work(
            engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            edges = await DerivedEdgeRepository().list_for_project(
                uow.connection, fixture.project_id
            )
            await uow.commit()
        assert len(edges) == first_pass.total_count
        assert all(edge.derived_from_commit == "deadbeef" for edge in edges)

        # A second recompute against a new commit must replace, not
        # accumulate: the prior generation's rows are gone afterward.
        (tmp_path / ".git" / "HEAD").write_text("cafef00d\n", encoding="utf-8")
        second_pass = await service.recompute_derived_edges(
            tenant_id=fixture.tenant_id, project_id=fixture.project_id
        )
        async with open_unit_of_work(
            engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            edges_after = await DerivedEdgeRepository().list_for_project(
                uow.connection, fixture.project_id
            )
            await uow.commit()
        assert len(edges_after) == second_pass.total_count
        assert all(edge.derived_from_commit == "cafef00d" for edge in edges_after)

        staleness = await service.staleness(
            tenant_id=fixture.tenant_id, project_id=fixture.project_id
        )
        assert staleness.stale_share == 0.0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_staleness_reports_nonzero_share_against_a_new_head_commit(
    tmp_path,
) -> None:
    (tmp_path / "engine").mkdir()
    (tmp_path / "engine" / "widget.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("deadbeef\n", encoding="utf-8")

    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = KnowledgeGraphService(engine, root=tmp_path)

        await service.recompute_derived_edges(
            tenant_id=fixture.tenant_id, project_id=fixture.project_id
        )

        (tmp_path / ".git" / "HEAD").write_text("cafef00d\n", encoding="utf-8")
        staleness = await service.staleness(
            tenant_id=fixture.tenant_id, project_id=fixture.project_id
        )
        assert staleness.head_commit == "cafef00d"
        assert staleness.stale_share == 1.0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_approving_a_task_graph_asserts_task_to_requirement_edges() -> None:
    """The real production mutation call site: `MissionService.
    create_task_graph` asserts a `task_to_requirement` `AssertedEdge` for
    every (task, requirement_ref) pair once the graph reaches `APPROVED`,
    and emits `KnowledgeGraphEdgeAsserted` through the same event/outbox
    mechanism every other module in this codebase uses."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        task_graphs = TaskGraphService(engine)
        service = MissionService(engine, EventService(engine), task_graphs=task_graphs)
        mission = await _create_mission(service, fixture, slug="MISSION-KG-001")

        graph_id = uuid7()
        planned = add_endpoint_template(mission, graph_id, SystemClock())
        digest = graph_hash(planned.tasks, planned.edges)

        graph = await service.create_task_graph(
            mission=mission,
            graph_id=graph_id,
            tasks=planned.tasks,
            edges=planned.edges,
            planning_mode="template",
            planner_policy_version=PLANNER_POLICY_VERSION,
            rationale=planned.rationale,
            created_by_principal=fixture.principal_id,
            approved_requirement_slugs={REQUIREMENT_SLUG},
        )
        assert graph.status == "APPROVED"
        assert graph.graph_hash == digest

        async with open_unit_of_work(
            engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            asserted = await AssertedEdgeRepository().list_for_project(
                uow.connection, fixture.project_id
            )
            events = await EventsRepository().list_events_for_aggregate(
                uow.connection, "asserted_edge", asserted[0].edge_id
            )
            await uow.commit()

        assert len(asserted) == len(planned.tasks) > 0
        assert all(edge.edge_type == "task_to_requirement" for edge in asserted)
        assert all(edge.target_key == f"ref:{REQUIREMENT_SLUG}" for edge in asserted)
        assert all(edge.status == "active" for edge in asserted)
        edge_task_ids = {edge.source_key.removeprefix("task:") for edge in asserted}
        assert edge_task_ids == {str(task.task_id) for task in planned.tasks}
        assert any(event.event_type == "KnowledgeGraphEdgeAsserted" for event in events)
    finally:
        await engine.dispose()
