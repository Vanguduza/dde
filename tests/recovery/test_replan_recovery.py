"""Chapter 19.1: a second session reconstructs a replan decision."""

from __future__ import annotations

import pytest

from engine.core.clock import SystemClock
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.missions.service import MissionService
from engine.planning.planner import PLANNER_POLICY_VERSION
from engine.planning.service import TaskGraphService
from engine.planning.templates import add_endpoint_template
from engine.recovery.dispatch import RecoveryService
from tests.support.db import new_engine, seed_tenant
from tests.unit.test_planning_postgres import REQUIREMENT_SLUG, _create_mission


@pytest.mark.asyncio
async def test_replan_survives_a_new_engine_session() -> None:
    writer = new_engine()
    try:
        fixture = await seed_tenant(writer)
        events = EventService(writer)
        graphs = TaskGraphService(writer)
        missions = MissionService(writer, events, task_graphs=graphs)
        mission = await _create_mission(
            missions, fixture, slug="MISSION-RECOVERY-REPLAN-SESSION"
        )
        graph_id = uuid7()
        planned = add_endpoint_template(mission, graph_id, SystemClock())
        graph = await missions.create_task_graph(
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
        active = await graphs.activate_task_graph(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            graph_id=graph_id,
            lock_version=graph.lock_version,
        )
        recovery = RecoveryService(
            writer, events=events, missions=missions, graphs=graphs
        )
        decision, new_graph = await recovery.replan(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=mission.mission_id,
            graph_id=active.graph_id,
            trigger="operator",
            created_by_principal=fixture.principal_id,
            approved_requirement_slugs={REQUIREMENT_SLUG},
            idempotency_key="recovery-replan-session-1",
        )
        tenant_id = fixture.tenant_id
        project_id = fixture.project_id
        new_graph_id = new_graph.graph_id
        trigger = decision.trigger
    finally:
        await writer.dispose()

    reader = new_engine()
    try:
        loaded = await TaskGraphService(reader).get_task_graph(
            tenant_id=tenant_id,
            project_id=project_id,
            graph_id=new_graph_id,
        )
        assert loaded.status == "ACTIVE"
        assert loaded.supersedes_id is not None
        assert trigger == "operator"
    finally:
        await reader.dispose()
