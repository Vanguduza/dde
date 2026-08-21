"""PostgreSQL-backed Mission Control projection + attention model (DDE-028)."""

from __future__ import annotations

import httpx
import pytest

from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.governance.hashing import approval_scope_hash
from engine.governance.service import ApprovalService
from engine.missions.service import MissionService
from engine.projections.service import MissionControlService
from tests.support.db import new_engine, seed_tenant
from tests.unit.test_gateway_api import _seed_grant
from tests.unit.test_planning_postgres import _active_graph_fixture


@pytest.mark.asyncio
async def test_projection_aggregates_durable_rows_and_pins_attention_metrics() -> None:
    engine = new_engine()
    try:
        (
            fixture,
            _service,
            _task_graphs,
            mission,
            _active,
            planned,
        ) = await _active_graph_fixture(engine, slug="MISSION-CTL-PROJ")
        approvals = ApprovalService(engine)
        digest = approval_scope_hash(
            approval_type="architecture_change",
            mission_id=mission.mission_id,
            payload={"plan": "a"},
        )
        requested = await approvals.request(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=mission.mission_id,
            approval_type="architecture_change",
            scope_hash=digest,
            requested_by=fixture.principal_id,
            idempotency_key="projection-approval-1",
        )
        await approvals.decide(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            approval_id=requested.approval_id,
            decision="APPROVED",
            decided_by=fixture.principal_id,
            rationale="same plan",
            scope_hash=digest,
            human_minutes=7.5,
        )

        projection = await MissionControlService(engine).project(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=mission.mission_id,
        )

        expected_counts: dict[str, int] = {}
        for task in planned.tasks:
            expected_counts[task.status] = expected_counts.get(task.status, 0) + 1

        assert projection.mission_id == mission.mission_id
        assert projection.task_total == len(planned.tasks)
        assert projection.task_counts == expected_counts
        assert projection.tasks_completed == expected_counts.get("COMPLETED", 0)
        assert projection.last_event_at is not None

        budget = await approvals.attention_budget(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=mission.mission_id,
        )
        assert projection.human_minutes == budget["human_minutes"] == 7.5
        assert projection.approvals_per_mission == budget["approvals_per_mission"] == 1
        assert projection.approvals_by_type == {"architecture_change": 1}
        assert projection.open_attention_items == budget["open_attention_items"] == 1
        assert projection.attention_debt == budget["attention_debt"] == 0
        assert projection.blocked_requests == budget["blocked_requests"] == 0
        assert (
            projection.standing_approval_usage == budget["standing_approval_usage"] == 0
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_mission_control_endpoint_authorizes_scope_tenant_and_project() -> None:
    engine = new_engine()
    from interfaces.api import app

    app.state.engine = engine
    try:
        fixture = await seed_tenant(engine)
        await _seed_grant(
            engine,
            tenant_id=fixture.tenant_id,
            principal_id=fixture.principal_id,
            project_id=fixture.project_id,
        )
        mission = await MissionService(engine, EventService(engine)).create_mission(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            slug=f"MISSION-CTL-HTTP-{uuid7().hex[:12]}",
            title="HTTP projection",
            intent="Endpoint wiring",
            success_definition="200 with projection",
            scope=["engine"],
            requirement_refs=[],
            autonomy_ceiling=1,
        )
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            opened = await client.post(
                "/v1/sessions",
                json={
                    "principal_id": str(fixture.principal_id),
                    "client_type": "human",
                    "scopes": ["mission.read"],
                    "subscriptions": ["mission"],
                },
            )
            session = opened.json()
            headers = {
                "X-Session-Id": session["session_id"],
                "X-Principal-Id": str(fixture.principal_id),
            }
            read = await client.get(
                f"/v1/mission-control/{mission.mission_id}", headers=headers
            )
            assert read.status_code == 200
            body = read.json()
            assert body["mission_id"] == str(mission.mission_id)
            assert body["task_total"] == 0

            # A session without mission.read must not read the projection.
            nosy = await client.post(
                "/v1/sessions",
                json={
                    "principal_id": str(fixture.principal_id),
                    "client_type": "human",
                    "scopes": ["mission.create"],
                    "subscriptions": [],
                },
            )
            denied = await client.get(
                f"/v1/mission-control/{mission.mission_id}",
                headers={
                    "X-Session-Id": nosy.json()["session_id"],
                    "X-Principal-Id": str(fixture.principal_id),
                },
            )
            assert denied.status_code == 403
            assert denied.json()["error_code"] == "FORBIDDEN"
    finally:
        app.state.engine = None
        await engine.dispose()


@pytest.mark.asyncio
async def test_mission_control_rejects_cross_tenant_mission() -> None:
    engine = new_engine()
    from interfaces.api import app

    app.state.engine = engine
    try:
        fixture = await seed_tenant(engine)
        other = await seed_tenant(engine)
        await _seed_grant(
            engine,
            tenant_id=fixture.tenant_id,
            principal_id=fixture.principal_id,
            project_id=fixture.project_id,
        )
        foreign = await MissionService(engine, EventService(engine)).create_mission(
            tenant_id=other.tenant_id,
            project_id=other.project_id,
            slug=f"MISSION-CTL-XTN-{uuid7().hex[:12]}",
            title="Other tenant",
            intent="Must not resolve",
            success_definition="403",
            scope=["engine"],
            requirement_refs=[],
            autonomy_ceiling=1,
        )
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            opened = await client.post(
                "/v1/sessions",
                json={
                    "principal_id": str(fixture.principal_id),
                    "client_type": "human",
                    "scopes": ["mission.read"],
                    "subscriptions": ["mission"],
                },
            )
            headers = {
                "X-Session-Id": opened.json()["session_id"],
                "X-Principal-Id": str(fixture.principal_id),
            }
            read = await client.get(
                f"/v1/mission-control/{foreign.mission_id}", headers=headers
            )
            assert read.status_code == 403
            assert read.json()["error_code"] == "TENANT_SCOPE_VIOLATION"
    finally:
        app.state.engine = None
        await engine.dispose()
