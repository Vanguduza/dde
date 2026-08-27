"""Chapter 16.5 load probe and fixture inventory (DDE-063)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from engine.core.ids import uuid7
from engine.gateway.app import app
from engine.load.inventory import missing_fixture_files
from engine.load.slo import (
    API_READ_P95_MS,
    COMMAND_ACCEPT_P95_MS,
    DEFAULT_SAMPLES,
    MEASURED_ROUTES,
    NOT_CLAIMED,
    RECONNECT_RECOVERY_MS,
    GatewaySloProbe,
)
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
    session_id: str,
    principal_id,
    target_type: str,
    target_id,
    command_type: str,
    parameters: dict,
) -> dict[str, object]:
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


def _mission_create_params(slug: str) -> dict[str, object]:
    return {
        "slug": slug,
        "title": "SLO mission",
        "intent": "Command acceptance probe",
        "success_definition": "Accepted via /v1/commands",
        "scope": ["engine"],
        "requirement_refs": [],
        "autonomy_ceiling": 1,
    }


def test_slo_fixture_files_exist() -> None:
    assert missing_fixture_files() == []


def test_capacity_statement_does_not_overclaim_healthz() -> None:
    assert "GET /v1/missions/{id}" in MEASURED_ROUTES
    assert "POST /v1/commands" in MEASURED_ROUTES
    assert "POST /v1/sessions/{id}/resume" in MEASURED_ROUTES
    assert any("QPS ceiling" in item for item in NOT_CLAIMED)
    assert any("WS/SSE" in item for item in NOT_CLAIMED)


@pytest.mark.asyncio
async def test_healthz_read_p95_under_slo() -> None:
    sample = await GatewaySloProbe().measure_healthz()
    assert sample.n >= 40
    assert sample.p95_ms < API_READ_P95_MS


@pytest.mark.asyncio
async def test_domain_read_command_accept_and_reconnect_under_slo() -> None:
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
        probe = GatewaySloProbe()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://slo.local"
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
            session_id = opened.json()["session_id"]
            headers = {
                "X-Session-Id": session_id,
                "X-Principal-Id": str(fixture.principal_id),
            }

            seed = await client.post(
                "/v1/commands",
                json=_command_body(
                    key=f"slo-seed-{uuid7().hex[:8]}",
                    session_id=session_id,
                    principal_id=fixture.principal_id,
                    target_type="project",
                    target_id=fixture.project_id,
                    command_type="mission.create",
                    parameters=_mission_create_params(f"MISSION-SLO-{uuid7().hex[:8]}"),
                ),
            )
            assert seed.status_code == 202
            mission_id = seed.json()["target_id"]

            read = await probe.measure_mission_read(
                client, mission_id=mission_id, headers=headers
            )
            assert read.n >= DEFAULT_SAMPLES
            assert read.p95_ms < API_READ_P95_MS

            burst = await probe.measure_mission_read_concurrent(
                client, mission_id=mission_id, headers=headers
            )
            assert burst.n >= 8
            assert burst.p95_ms < API_READ_P95_MS

            bodies = [
                _command_body(
                    key=f"slo-accept-{i}-{uuid7().hex[:8]}",
                    session_id=session_id,
                    principal_id=fixture.principal_id,
                    target_type="project",
                    target_id=fixture.project_id,
                    command_type="mission.create",
                    parameters=_mission_create_params(
                        f"MISSION-SLOA-{i}-{uuid7().hex[:8]}"
                    ),
                )
                for i in range(DEFAULT_SAMPLES)
            ]
            accepted = await probe.measure_command_acceptance(client, bodies=bodies)
            assert accepted.n >= DEFAULT_SAMPLES
            assert accepted.p95_ms < COMMAND_ACCEPT_P95_MS

            cursor = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
            reconnect = await probe.measure_reconnect(
                client, session_id=session_id, last_event_at=cursor
            )
            assert reconnect.n >= DEFAULT_SAMPLES
            assert reconnect.p95_ms < RECONNECT_RECOVERY_MS
            assert reconnect.max_ms < RECONNECT_RECOVERY_MS
    finally:
        app.state.engine = None
        await engine.dispose()
