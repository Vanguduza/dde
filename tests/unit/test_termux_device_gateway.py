"""DDE-054 live Gateway proofs: device session + device.heartbeat.

Pins Ch.14.2 device baseline (no mission scopes), required device_id,
COMMAND_SCOPES routing for device.heartbeat under device.command, and
Ch.15.2 idempotent acceptance. Does not claim WS/SSE replay (EDR-0027)
or a rich device command surface (EDR-0030).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
from sqlalchemy import text

from engine.core.ids import uuid7
from engine.gateway.scopes import COMMAND_SCOPES, COMMAND_TARGET_TYPE
from engine.governance.config import RuntimeFlags, validate_configuration
from interfaces.api import app
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


def test_device_heartbeat_bound_in_command_scopes() -> None:
    assert COMMAND_SCOPES["device.heartbeat"] == "device.command"
    assert COMMAND_TARGET_TYPE["device.heartbeat"] == "device"


def test_android_offline_queue_flag_defaults_off() -> None:
    flags = RuntimeFlags()
    assert flags.android_offline_queue_enabled is False
    validate_configuration(flags)


@pytest.mark.asyncio
async def test_device_session_requires_device_id() -> None:
    engine = new_engine()
    app.state.engine = engine
    try:
        fixture = await seed_tenant(engine)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            missing = await client.post(
                "/v1/sessions",
                json={
                    "principal_id": str(fixture.principal_id),
                    "client_type": "device",
                    "scopes": ["device.read", "device.command"],
                    "subscriptions": [],
                },
            )
            assert missing.status_code == 403
            assert missing.json()["error_code"] == "FORBIDDEN"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_device_session_rejects_mission_scopes() -> None:
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
                    "client_type": "device",
                    "device_id": str(uuid7()),
                    "scopes": ["device.read", "mission.read"],
                    "subscriptions": [],
                },
            )
            assert refused.status_code == 403
            assert refused.json()["error_code"] == "FORBIDDEN"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_device_heartbeat_accepted_and_idempotent() -> None:
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
        device_id = uuid7()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            opened = await client.post(
                "/v1/sessions",
                json={
                    "principal_id": str(fixture.principal_id),
                    "client_type": "device",
                    "device_id": str(device_id),
                    "scopes": ["device.read", "device.command"],
                    "subscriptions": [],
                },
            )
            assert opened.status_code == 201
            session = opened.json()
            assert session["client_type"] == "device"
            assert UUID(session["device_id"]) == device_id
            session_id = session["session_id"]

            key = f"device-hb-{uuid7().hex[:12]}"
            body = _command_body(
                key=key,
                session_id=session_id,
                principal_id=fixture.principal_id,
                target_type="device",
                target_id=device_id,
                command_type="device.heartbeat",
                parameters={"project_id": str(fixture.project_id)},
            )
            first = await client.post("/v1/commands", json=body)
            assert first.status_code == 202
            accepted = first.json()
            assert accepted["status"] == "accepted"
            assert accepted["target_type"] == "device"
            assert UUID(accepted["target_id"]) == device_id
            assert accepted["payload"]["ok"] is True

            # Same command_id + idempotency_key + body → ledger replay,
            # not a second mutation.
            second = await client.post("/v1/commands", json=body)
            assert second.status_code == 202
            assert second.json()["command_id"] == accepted["command_id"]
            assert second.json()["payload"]["ok"] is True

            # Device session cannot mint mission mutations.
            mission_try = await client.post(
                "/v1/commands",
                json=_command_body(
                    key=f"device-mission-{uuid7().hex[:8]}",
                    session_id=session_id,
                    principal_id=fixture.principal_id,
                    target_type="project",
                    target_id=fixture.project_id,
                    command_type="mission.create",
                    parameters={
                        "slug": f"MISSION-DEV-{uuid7().hex[:8]}",
                        "title": "should fail",
                        "intent": "device must not create",
                        "success_definition": "n/a",
                        "scope": [],
                        "requirement_refs": [],
                        "autonomy_ceiling": 1,
                    },
                ),
            )
            assert mission_try.status_code == 403
            assert mission_try.json()["error_code"] == "FORBIDDEN"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_device_heartbeat_rejects_mismatched_device_id() -> None:
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
        device_id = uuid7()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            opened = await client.post(
                "/v1/sessions",
                json={
                    "principal_id": str(fixture.principal_id),
                    "client_type": "device",
                    "device_id": str(device_id),
                    "scopes": ["device.command"],
                    "subscriptions": [],
                },
            )
            assert opened.status_code == 201
            session_id = opened.json()["session_id"]
            bad = await client.post(
                "/v1/commands",
                json=_command_body(
                    key=f"device-hb-bad-{uuid7().hex[:8]}",
                    session_id=session_id,
                    principal_id=fixture.principal_id,
                    target_type="device",
                    target_id=uuid7(),
                    command_type="device.heartbeat",
                    parameters={"project_id": str(fixture.project_id)},
                ),
            )
            assert bad.status_code == 403
            assert bad.json()["error_code"] == "FORBIDDEN"
    finally:
        await engine.dispose()
