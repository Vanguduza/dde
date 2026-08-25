"""Gateway command path for OpenSandbox capture — raw key never in response."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import text

from engine.core.ids import uuid7
from interfaces.api import app
from tests.support.db import new_engine, seed_tenant

RAW_KEY = "osk_gateway_capture_raw_secret_xyz"

_VAULT_DDL = """
CREATE TABLE IF NOT EXISTS broker_static_secret_material (
    capture_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    provider_id text NOT NULL,
    secret_value text NOT NULL,
    created_at timestamptz NOT NULL,
    PRIMARY KEY (capture_id)
);
"""


async def _seed_grant(engine, *, tenant_id, principal_id, project_id) -> None:
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


async def _open_session(client: httpx.AsyncClient, fixture, scopes: list[str]) -> dict:
    opened = await client.post(
        "/v1/sessions",
        json={
            "principal_id": str(fixture.principal_id),
            "client_type": "human",
            "scopes": scopes,
            "subscriptions": [],
        },
    )
    assert opened.status_code == 201, opened.text
    return opened.json()


@pytest.mark.asyncio
async def test_gateway_capture_opensandbox_redacts_raw_key() -> None:
    engine = new_engine()
    async with engine.connect() as connection:
        await connection.execute(text(_VAULT_DDL))
        await connection.commit()
    fixture = await seed_tenant(engine)
    await _seed_grant(
        engine,
        tenant_id=fixture.tenant_id,
        principal_id=fixture.principal_id,
        project_id=fixture.project_id,
    )
    app.state.engine = engine
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session = await _open_session(
            client,
            fixture,
            ["mission.read", "credential.capture"],
        )
        response = await client.post(
            "/v1/commands",
            json={
                "command_id": str(uuid7()),
                "idempotency_key": f"osb-capture-{uuid7()}",
                "principal_id": str(fixture.principal_id),
                "client_session_id": session["session_id"],
                "target_type": "project",
                "target_id": str(fixture.project_id),
                "command_type": "credential.capture_opensandbox",
                "parameters": {"api_key": RAW_KEY, "domain": "gw.example"},
                "requested_at": datetime.now(UTC).isoformat(),
                "protocol_version": "1",
            },
        )
    assert response.status_code == 202, response.text
    body = response.json()
    assert RAW_KEY not in response.text
    assert body["payload"]["captured"] is True
    assert "fingerprint" in body["payload"]
    assert body["payload"]["last4"] == RAW_KEY[-4:]
    assert "api_key" not in body["payload"]
    assert "secret_value" not in body["payload"]
    await engine.dispose()
