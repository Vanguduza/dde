"""DDE-055 live Gateway proofs: messaging scopes have no decide authority.

Pins Ch.14.2 / Ch.15.1 at the Gateway session boundary the messaging
bridge must use. Does not claim vendor Slack/Telegram SDKs (EDR-0031).
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import text

from engine.core.ids import uuid7
from interfaces.api import app
from interfaces.messaging.scopes import MESSAGING_SCOPES
from tests.support.db import new_engine, seed_tenant


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


def _command_body(**kwargs) -> dict:
    return {
        "command_id": str(uuid7()),
        "idempotency_key": kwargs["key"],
        "principal_id": str(kwargs["principal_id"]),
        "client_session_id": str(kwargs["session_id"]),
        "target_type": kwargs["target_type"],
        "target_id": str(kwargs["target_id"]),
        "command_type": kwargs["command_type"],
        "parameters": kwargs.get("parameters", {}),
        "requested_at": datetime.now(UTC).isoformat(),
        "protocol_version": "1",
    }


@pytest.mark.asyncio
async def test_messaging_service_session_allowlist_opens() -> None:
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
                    "client_type": "service",
                    "scopes": list(MESSAGING_SCOPES),
                    "subscriptions": ["mission"],
                },
            )
            assert opened.status_code == 201
            assert set(opened.json()["scopes"]) == set(MESSAGING_SCOPES)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_messaging_service_session_rejects_decide() -> None:
    engine = new_engine()
    app.state.engine = engine
    try:
        fixture = await seed_tenant(engine)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            refused = await client.post(
                "/v1/sessions",
                json={
                    "principal_id": str(fixture.principal_id),
                    "client_type": "service",
                    "scopes": ["mission.read", "approval.decide"],
                    "subscriptions": [],
                },
            )
            assert refused.status_code == 403
            assert refused.json()["error_code"] == "FORBIDDEN"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_messaging_scopes_can_control_but_not_batch_decide() -> None:
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
            # Human creates a mission (messaging allowlist excludes create).
            human = await client.post(
                "/v1/sessions",
                json={
                    "principal_id": str(fixture.principal_id),
                    "client_type": "human",
                    "scopes": ["mission.read", "mission.create", "mission.control"],
                    "subscriptions": [],
                },
            )
            assert human.status_code == 201
            human_sid = human.json()["session_id"]
            created = await client.post(
                "/v1/commands",
                json=_command_body(
                    key=f"msg-create-{uuid7().hex[:8]}",
                    session_id=human_sid,
                    principal_id=fixture.principal_id,
                    target_type="project",
                    target_id=fixture.project_id,
                    command_type="mission.create",
                    parameters={
                        "slug": f"MISSION-MSG-{uuid7().hex[:8]}",
                        "title": "Messaging control fixture",
                        "intent": "prove transport control",
                        "success_definition": "paused once",
                        "scope": [],
                        "requirement_refs": [],
                        "autonomy_ceiling": 1,
                    },
                ),
            )
            assert created.status_code == 202
            mission_id = created.json()["target_id"]

            messaging = await client.post(
                "/v1/sessions",
                json={
                    "principal_id": str(fixture.principal_id),
                    "client_type": "service",
                    "scopes": list(MESSAGING_SCOPES),
                    "subscriptions": [],
                },
            )
            assert messaging.status_code == 201
            msg_sid = messaging.json()["session_id"]

            cancelled = await client.post(
                "/v1/commands",
                json=_command_body(
                    key=f"msg-cancel-{uuid7().hex[:8]}",
                    session_id=msg_sid,
                    principal_id=fixture.principal_id,
                    target_type="mission",
                    target_id=mission_id,
                    command_type="mission.cancel",
                    parameters={"lock_version": 1},
                ),
            )
            assert cancelled.status_code == 202
            assert cancelled.json()["status"] == "accepted"

            decide = await client.post(
                "/v1/commands",
                json=_command_body(
                    key=f"msg-decide-{uuid7().hex[:8]}",
                    session_id=msg_sid,
                    principal_id=fixture.principal_id,
                    target_type="project",
                    target_id=fixture.project_id,
                    command_type="approval.batch_decide",
                    parameters={
                        "decision": "APPROVE",
                        "approval_ids": [str(uuid7())],
                        "rationale": "messaging must not decide",
                    },
                ),
            )
            assert decide.status_code == 403
            assert decide.json()["error_code"] == "FORBIDDEN"
    finally:
        await engine.dispose()
