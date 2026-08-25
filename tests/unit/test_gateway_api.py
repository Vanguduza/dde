"""HTTP surface tests for the gateway (DDE-027, Ch.15.1/15.2)."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from engine.core.ids import uuid7
from interfaces.api import app
from tests.support.db import new_engine, seed_tenant


async def _seed_grant(engine, *, tenant_id, principal_id, project_id) -> None:
    from sqlalchemy import text

    now = datetime.now(UTC)
    async with engine.connect() as connection:
        await connection.execute(
            text(
                "INSERT INTO principal_grants "
                "(grant_id, tenant_id, project_id, principal_id, scope_type, "
                "grant_scope, created_at, updated_at) "
                "VALUES (:grant_id, :tenant_id, :project_id, :principal_id, 'PROJECT', 'PROJECT', :now, :now)"
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


def _mission_create_params() -> dict:
    return {
        "slug": f"MISSION-GW-{uuid7().hex[:12]}",
        "title": "Gateway mission",
        "intent": "Acceptance path",
        "success_definition": "Created via /v1/commands",
        "scope": ["engine"],
        "requirement_refs": [],
        "autonomy_ceiling": 1,
    }


@pytest.mark.asyncio
async def test_session_and_command_acceptance_flow() -> None:
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
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            opened = await client.post(
                "/v1/sessions",
                json={
                    "principal_id": str(fixture.principal_id),
                    "client_type": "human",
                    "scopes": ["mission.read", "mission.create", "mission.control"],
                    "subscriptions": ["mission"],
                },
            )
            assert opened.status_code == 201
            session = opened.json()
            assert session["tenant_id"] == str(fixture.tenant_id)

            body = _command_body(
                key="mission-create-1",
                session_id=session["session_id"],
                principal_id=fixture.principal_id,
                target_type="project",
                target_id=fixture.project_id,
                command_type="mission.create",
                parameters=_mission_create_params(),
            )
            accepted = await client.post("/v1/commands", json=body)
            assert accepted.status_code == 202
            mission_id = accepted.json()["target_id"]

            # Same command, same idempotency key: no second mutation.
            replayed = await client.post("/v1/commands", json=body)
            assert replayed.status_code == 202
            assert replayed.json()["status"] == "completed"
            assert replayed.json()["target_id"] == mission_id

            read = await client.get(
                f"/v1/missions/{mission_id}",
                headers={
                    "X-Session-Id": session["session_id"],
                    "X-Principal-Id": str(fixture.principal_id),
                },
            )
            assert read.status_code == 200
            assert read.json()["mission_id"] == mission_id
    finally:
        app.state.engine = None
        await engine.dispose()


@pytest.mark.asyncio
async def test_command_without_scope_is_forbidden() -> None:
    engine = new_engine()
    app.state.engine = engine
    try:
        fixture = await seed_tenant(engine)
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
                    "subscriptions": [],
                },
            )
            session = opened.json()
            body = _command_body(
                key="mission-create-denied",
                session_id=session["session_id"],
                principal_id=fixture.principal_id,
                target_type="project",
                target_id=fixture.project_id,
                command_type="mission.create",
                parameters=_mission_create_params(),
            )
            denied = await client.post("/v1/commands", json=body)
            assert denied.status_code == 403
            assert denied.json()["error_code"] == "FORBIDDEN"
    finally:
        app.state.engine = None
        await engine.dispose()
