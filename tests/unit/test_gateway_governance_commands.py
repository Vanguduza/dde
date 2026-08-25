"""Gateway command-path tests for the Chapter 13.1 governance commands:
`approval.batch_decide`, `approval.request_budget_increase` and
`approval.decide_budget_increase` through POST /v1/commands (Ch.15.1/15.4).

These exercise the real fail-closed order — session scope, project grant,
gateway ledger, then the governance service's own ledger and state machine
— against PostgreSQL, like the other gateway acceptance tests."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import text

from engine.context.repo import repo_root
from engine.core.ids import uuid7
from engine.governance.hashing import approval_scope_hash
from engine.workspaces.service import WorkspaceService
from interfaces.api import app
from tests.support.db import new_engine, seed_tenant
from tests.support.worker_fixtures import build_worker_fixture


async def _seed_grant(engine, *, tenant_id, principal_id, project_id) -> None:
    now = datetime.now(UTC)
    async with engine.connect() as connection:
        await connection.execute(
            text(
                "INSERT INTO principal_grants "
                "(grant_id, tenant_id, project_id, principal_id, scope_type, "
                "grant_scope, created_at, updated_at) "
                "VALUES (:grant_id, :tenant_id, :project_id, :principal_id, "
                "'PROJECT', 'PROJECT', :now, :now)"
            ),
            {
                "grant_id": uuid7(),
                "tenant_id": tenant_id,
                "project_id": project_id,
                "principal_id": principal_id,
                "now": now,
            },
        )
        await connection.commit()


def _command_body(
    *,
    key: str,
    session_id,
    principal_id,
    target_type,
    target_id,
    command_type,
    parameters,
) -> dict:
    return {
        "command_id": str(uuid7()),
        "idempotency_key": key,
        "principal_id": str(principal_id),
        "client_session_id": str(session_id),
        "target_type": target_type,
        "target_id": str(target_id),
        "command_type": command_type,
        "parameters": parameters,
        "requested_at": datetime.now(UTC).isoformat(),
        "protocol_version": "1",
    }


async def _open_session(client: httpx.AsyncClient, fixture, scopes: list[str]) -> dict:
    opened = await client.post(
        "/v1/sessions",
        json={
            "principal_id": str(fixture.principal_id),
            "client_type": "human",
            "scopes": scopes,
            "subscriptions": ["approval"],
        },
    )
    assert opened.status_code == 201, opened.text
    return opened.json()


async def _seed_mission(engine, fixture) -> object:
    from engine.events.service import EventService
    from engine.missions.service import MissionService

    missions = MissionService(engine, EventService(engine))
    mission = await missions.create_mission(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        slug=f"MISSION-GW-APR-{uuid7().hex[:12]}",
        title="Gateway approvals",
        intent="Approval commands over /v1/commands",
        success_definition="Batch decided through the gateway",
        scope=["engine"],
        requirement_refs=[],
        autonomy_ceiling=2,
    )
    return mission


async def _seed_pending_approval(
    engine, fixture, mission_id, *, key: str, tag: str
) -> tuple[object, str]:
    from engine.governance.service import ApprovalService

    service = ApprovalService(engine)
    digest = approval_scope_hash(
        approval_type="architecture_change",
        mission_id=mission_id,
        payload={"tag": tag},
    )
    approval = await service.request(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        mission_id=mission_id,
        approval_type="architecture_change",
        scope_hash=digest,
        requested_by=fixture.principal_id,
        idempotency_key=key,
    )
    return approval, digest


@pytest.mark.asyncio
async def test_batch_decide_command_round_trip_and_replay() -> None:
    """Happy path: a human session holding `approval.decide` decides two
    pending approvals as one all-or-nothing batch through POST
    /v1/commands; replaying the same idempotency key returns the stored
    first outcome without re-deciding."""
    engine = new_engine()
    app.state.engine = engine
    try:
        fixture = await seed_tenant(engine)
        await _seed_grant(
            engine,
            tenant_id=fixture.tenant_id,
            principal_id=fixture.principal_id,
            project_id=fixture.project_id,
        )
        mission = await _seed_mission(engine, fixture)
        first, digest_first = await _seed_pending_approval(
            engine, fixture, mission.mission_id, key="gw-batch-a", tag="a"
        )
        second, digest_second = await _seed_pending_approval(
            engine, fixture, mission.mission_id, key="gw-batch-b", tag="b"
        )
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            session = await _open_session(
                client,
                fixture,
                ["mission.read", "approval.read", "approval.decide"],
            )
            body = _command_body(
                key=f"approval-batch-{uuid7().hex}",
                session_id=session["session_id"],
                principal_id=fixture.principal_id,
                target_type="project",
                target_id=fixture.project_id,
                command_type="approval.batch_decide",
                parameters={
                    "approval_ids": [
                        str(first.approval_id),
                        str(second.approval_id),
                    ],
                    "scope_hashes": [digest_first, digest_second],
                    "decision": "APPROVED",
                    "rationale": "gateway batch",
                    "human_minutes": 2,
                },
            )
            accepted = await client.post("/v1/commands", json=body)
            assert accepted.status_code == 202, accepted.text
            payload = accepted.json()
            assert payload["target_type"] == "approval_batch"
            assert payload["payload"]["decision"] == "APPROVED"
            assert payload["payload"]["member_count"] == 2
            assert payload["payload"]["replayed"] is False
            assert payload["payload"]["batch_id"] is not None
            member_statuses = sorted(
                item["status"] for item in payload["payload"]["approvals"]
            )
            assert member_statuses == ["APPROVED", "APPROVED"]

            # Same command, same idempotency key: no second decision pass.
            replayed = await client.post("/v1/commands", json=body)
            assert replayed.status_code == 202
            replay_payload = replayed.json()
            assert replay_payload["command_id"] == payload["command_id"]
            assert replay_payload["target_id"] == payload["target_id"]
            assert (
                replay_payload["payload"]["approvals"]
                == payload["payload"]["approvals"]
            )
    finally:
        app.state.engine = None
        await engine.dispose()


@pytest.mark.asyncio
async def test_batch_decide_without_decide_scope_is_forbidden() -> None:
    """A human session that never requested `approval.decide` is refused
    at the gateway authorization layer before any governance write."""
    engine = new_engine()
    app.state.engine = engine
    try:
        fixture = await seed_tenant(engine)
        await _seed_grant(
            engine,
            tenant_id=fixture.tenant_id,
            principal_id=fixture.principal_id,
            project_id=fixture.project_id,
        )
        mission = await _seed_mission(engine, fixture)
        approval, digest = await _seed_pending_approval(
            engine, fixture, mission.mission_id, key="gw-noscope-a", tag="noscope"
        )
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            session = await _open_session(
                client,
                fixture,
                ["mission.read", "approval.read"],
            )
            body = _command_body(
                key=f"approval-batch-denied-{uuid7().hex}",
                session_id=session["session_id"],
                principal_id=fixture.principal_id,
                target_type="project",
                target_id=fixture.project_id,
                command_type="approval.batch_decide",
                parameters={
                    "approval_ids": [str(approval.approval_id)],
                    "scope_hashes": [digest],
                    "decision": "APPROVED",
                    "rationale": "should be refused",
                },
            )
            denied = await client.post("/v1/commands", json=body)
            assert denied.status_code == 403
            assert denied.json()["error_code"] == "FORBIDDEN"
    finally:
        app.state.engine = None
        await engine.dispose()


@pytest.mark.asyncio
async def test_unknown_command_type_is_still_forbidden() -> None:
    """The routing table stays fail-closed: an unknown approval-shaped
    command type must not slip through because its prefix looks familiar."""
    engine = new_engine()
    app.state.engine = engine
    try:
        fixture = await seed_tenant(engine)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            session = await _open_session(
                client,
                fixture,
                ["mission.read", "approval.read", "approval.decide"],
            )
            body = _command_body(
                key=f"unknown-cmd-{uuid7().hex}",
                session_id=session["session_id"],
                principal_id=fixture.principal_id,
                target_type="project",
                target_id=fixture.project_id,
                command_type="approval.self_grant",
                parameters={},
            )
            denied = await client.post("/v1/commands", json=body)
            assert denied.status_code == 403
            assert denied.json()["error_code"] == "FORBIDDEN"
    finally:
        app.state.engine = None
        await engine.dispose()


@pytest.mark.asyncio
async def test_budget_increase_request_then_decision_round_trip(
    tmp_path,
) -> None:
    """Request half + decide half of the Ch.7.1/12.3 budget workflow over
    POST /v1/commands: the request mints a bound `budget_increase`
    approval; the decision grants a new ACTIVE plan carrying the raised
    ceiling. The task comes from the real fixture chain so the grant's
    re-plan step has a genuine ExecutionPlan to supersede."""
    root = repo_root()
    engine = new_engine()
    app.state.engine = engine
    workspace = None
    try:
        fixture = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-GW-BUDGET"
        )
        workspace = fixture.workspace
        tenant = fixture.tenant
        await _seed_grant(
            engine,
            tenant_id=tenant.tenant_id,
            principal_id=tenant.principal_id,
            project_id=tenant.project_id,
        )
        mission_id = fixture.mission.mission_id
        task_id = fixture.task.task_id

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            session = await _open_session(
                client,
                tenant,
                [
                    "mission.read",
                    "approval.read",
                    "approval.decide",
                    "approval.request",
                ],
            )

            request_body = _command_body(
                key=f"budget-request-{uuid7().hex}",
                session_id=session["session_id"],
                principal_id=tenant.principal_id,
                target_type="project",
                target_id=tenant.project_id,
                command_type="approval.request_budget_increase",
                parameters={
                    "mission_id": str(mission_id),
                    "task_id": str(task_id),
                    "reason": "verification attempt needs more tokens",
                    "requested_max_tokens": 200000,
                },
            )
            requested = await client.post("/v1/commands", json=request_body)
            assert requested.status_code == 202, requested.text
            request_payload = requested.json()
            assert request_payload["target_type"] == "budget_request"
            assert request_payload["payload"]["requested_max_tokens"] == 200000
            assert request_payload["payload"]["task_id"] == str(task_id)
            approval_id = request_payload["payload"]["approval_id"]

            decide_body = _command_body(
                key=f"budget-decision-{uuid7().hex}",
                session_id=session["session_id"],
                principal_id=tenant.principal_id,
                target_type="project",
                target_id=tenant.project_id,
                command_type="approval.decide_budget_increase",
                parameters={
                    "approval_id": approval_id,
                    "decision": "APPROVED",
                    "rationale": "verified need",
                    "human_minutes": 3,
                },
            )
            decided = await client.post("/v1/commands", json=decide_body)
            assert decided.status_code == 202, decided.text
            decide_payload = decided.json()["payload"]
            assert decide_payload["granted"] is True
            assert decide_payload["granted_max_tokens"] == 200000
            assert decide_payload["plan_id"] is not None
            assert decide_payload["plan_id"] != str(fixture.execution_plan.plan_id)
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=root).cleanup(workspace=workspace)
        app.state.engine = None
        await engine.dispose()
