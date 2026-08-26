"""DDE-052 web dashboard: Gateway-mounted assets + Ch.13.9 scoped reads."""

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


def _mission_params(slug: str) -> dict:
    return {
        "slug": slug,
        "title": "Dashboard mission",
        "intent": "Prove web dashboard Gateway path",
        "success_definition": "Readable via /dashboard client path",
        "scope": ["engine"],
        "requirement_refs": [],
        "autonomy_ceiling": 1,
    }


@pytest.mark.asyncio
async def test_dashboard_static_shell_is_mounted() -> None:
    engine = new_engine()
    app.state.engine = engine
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            index = await client.get("/dashboard/")
            assert index.status_code == 200
            assert "DDE" in index.text
            assert "Gateway client" in index.text
            gateway_js = await client.get("/dashboard/gateway.js")
            assert gateway_js.status_code == 200
            assert "GatewayApiClient" in gateway_js.text
            app_js = await client.get("/dashboard/app.js")
            assert app_js.status_code == 200
            assert "mission.pause" in app_js.text
    finally:
        app.state.engine = None
        await engine.dispose()


@pytest.mark.asyncio
async def test_dashboard_path_reads_mission_and_control() -> None:
    """Same /v1 reads the browser client performs after Open session."""
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
            created = await client.post(
                "/v1/commands",
                json=_command_body(
                    key=f"dash-create-{uuid7().hex[:8]}",
                    session_id=session["session_id"],
                    principal_id=fixture.principal_id,
                    target_type="project",
                    target_id=fixture.project_id,
                    command_type="mission.create",
                    parameters=_mission_params(f"MISSION-DASH-{uuid7().hex[:8]}"),
                ),
            )
            assert created.status_code == 202
            mission_id = created.json()["target_id"]
            headers = {
                "X-Session-Id": session["session_id"],
                "X-Principal-Id": str(fixture.principal_id),
            }
            mission = await client.get(f"/v1/missions/{mission_id}", headers=headers)
            control = await client.get(
                f"/v1/mission-control/{mission_id}", headers=headers
            )
            assert mission.status_code == 200
            assert control.status_code == 200
            assert mission.json()["mission_id"] == mission_id
            assert control.json()["mission_id"] == mission_id
    finally:
        app.state.engine = None
        await engine.dispose()


@pytest.mark.asyncio
async def test_dashboard_path_rejects_cross_tenant_mission_read() -> None:
    """Ch.13.9: dashboard applies the same authorization scope as API reads."""
    engine = new_engine()
    app.state.engine = engine
    try:
        owner = await seed_tenant(engine)
        stranger = await seed_tenant(engine)
        await _seed_grant(
            engine,
            tenant_id=owner.tenant_id,
            principal_id=owner.principal_id,
            project_id=owner.project_id,
        )
        await _seed_grant(
            engine,
            tenant_id=stranger.tenant_id,
            principal_id=stranger.principal_id,
            project_id=stranger.project_id,
        )
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            owner_session = (
                await client.post(
                    "/v1/sessions",
                    json={
                        "principal_id": str(owner.principal_id),
                        "client_type": "human",
                        "scopes": [
                            "mission.read",
                            "mission.create",
                            "mission.control",
                        ],
                        "subscriptions": ["mission"],
                    },
                )
            ).json()
            created = await client.post(
                "/v1/commands",
                json=_command_body(
                    key=f"dash-cross-{uuid7().hex[:8]}",
                    session_id=owner_session["session_id"],
                    principal_id=owner.principal_id,
                    target_type="project",
                    target_id=owner.project_id,
                    command_type="mission.create",
                    parameters=_mission_params(f"MISSION-X-{uuid7().hex[:8]}"),
                ),
            )
            assert created.status_code == 202
            mission_id = created.json()["target_id"]

            stranger_session = (
                await client.post(
                    "/v1/sessions",
                    json={
                        "principal_id": str(stranger.principal_id),
                        "client_type": "human",
                        "scopes": ["mission.read"],
                        "subscriptions": [],
                    },
                )
            ).json()
            denied = await client.get(
                f"/v1/missions/{mission_id}",
                headers={
                    "X-Session-Id": stranger_session["session_id"],
                    "X-Principal-Id": str(stranger.principal_id),
                },
            )
            assert denied.status_code in {403, 404}
            body = denied.json()
            assert body.get("error_code") in {
                "TENANT_SCOPE_VIOLATION",
                "FORBIDDEN",
                "POLICY_DENIED",
                "NOT_FOUND",
            }
            control_denied = await client.get(
                f"/v1/mission-control/{mission_id}",
                headers={
                    "X-Session-Id": stranger_session["session_id"],
                    "X-Principal-Id": str(stranger.principal_id),
                },
            )
            assert control_denied.status_code in {403, 404}
    finally:
        app.state.engine = None
        await engine.dispose()
