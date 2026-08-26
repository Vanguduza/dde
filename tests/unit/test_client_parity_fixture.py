"""DDE-056 golden CLI / web / Android client-parity fixture.

Proves S6 exit criteria for the client track:
- identical authoritative outcomes on one golden mission across CLI,
  dashboard (web), and Android Gateway allowlists;
- reconnect (resume + by-id re-sync) without duplicate commands via
  idempotency replay.

Does not claim full WS/SSE sequence replay (EDR-0027).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from engine.core.ids import uuid7
from interfaces.api import app
from interfaces.cli.gateway_client import ALLOWED_PATHS, GatewayClient
from tests.support.db import new_engine, seed_tenant

ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_GATEWAY = ROOT / "interfaces" / "dashboard" / "static" / "gateway.js"
ANDROID_ALLOWLIST = (
    ROOT
    / "interfaces"
    / "android"
    / "gateway"
    / "src"
    / "main"
    / "kotlin"
    / "dev"
    / "dde"
    / "android"
    / "gateway"
    / "GatewayAllowlist.kt"
)

CLIENTS = ("cli", "web", "android")

_AUTHORITATIVE_MISSION_KEYS = (
    "mission_id",
    "tenant_id",
    "project_id",
    "slug",
    "title",
    "status",
    "autonomy_ceiling",
    "lock_version",
)


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


def _extract_js_allowed_paths(source: str) -> list[str]:
    block = re.search(
        r"ALLOWED_PATHS\s*=\s*Object\.freeze\(\[([^\]]+)\]\)",
        source,
        re.DOTALL,
    )
    assert block is not None, "dashboard gateway.js missing ALLOWED_PATHS"
    return re.findall(r'"([^"]+)"', block.group(1))


def _extract_kotlin_allowed_paths(source: str) -> list[str]:
    block = re.search(
        r"ALLOWED_PATHS[^=]*=\s*listOf\(([^)]+)\)",
        source,
        re.DOTALL,
    )
    assert block is not None, "Android GatewayAllowlist missing ALLOWED_PATHS"
    return re.findall(r'"([^"]+)"', block.group(1))


def _mission_slice(mission: dict) -> dict:
    return {key: mission[key] for key in _AUTHORITATIVE_MISSION_KEYS}


def _control_slice(control: dict) -> dict:
    return {
        "mission_id": control["mission_id"],
        "status": control["status"],
        "task_total": control.get("task_total"),
        "tasks_completed": control.get("tasks_completed"),
    }


def test_allowlists_identical_across_cli_web_android() -> None:
    """Reuse the dashboard/android/termux six-path surface — no new lists."""
    expected = list(ALLOWED_PATHS)
    js_paths = _extract_js_allowed_paths(DASHBOARD_GATEWAY.read_text(encoding="utf-8"))
    kt_paths = _extract_kotlin_allowed_paths(
        ANDROID_ALLOWLIST.read_text(encoding="utf-8")
    )
    assert js_paths == expected
    assert kt_paths == expected
    # Honesty: no invented collection endpoints.
    joined = "\n".join(expected)
    assert "/v1/missions/{id}" in joined
    assert 'GET /v1/missions"' not in joined
    assert "events" not in joined.lower()


@pytest.mark.asyncio
async def test_golden_mission_identical_outcomes_cli_web_android() -> None:
    """One golden mission; CLI/web/Android Gateway paths agree on authority."""
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
        ) as http:
            # CLI creates the golden mission (same allowlist as web/Android).
            cli = GatewayClient(http)
            opened = await cli.open_session(
                principal_id=str(fixture.principal_id),
            )
            session_id = opened["session_id"]
            slug = f"MISSION-PARITY-{uuid7().hex[:8]}"
            status, accepted = await cli.accept_command(
                session_id=session_id,
                principal_id=str(fixture.principal_id),
                command_type="mission.create",
                target_type="project",
                target_id=str(fixture.project_id),
                parameters={
                    "slug": slug,
                    "title": "DDE-056 golden parity mission",
                    "intent": "Identical CLI/web/Android authoritative outcomes",
                    "success_definition": "All three clients read the same status",
                    "scope": ["engine"],
                    "requirement_refs": [],
                    "autonomy_ceiling": 1,
                },
                idempotency_key=f"parity-create-{uuid7().hex[:8]}",
            )
            assert status == 202, accepted
            mission_id = accepted["target_id"]
            # Acceptance is not completion — re-read by id (Ch.15.2).
            assert accepted.get("command_id")
            assert mission_id

            views: dict[str, tuple[dict, dict]] = {}
            for label in CLIENTS:
                client = GatewayClient(http)
                session = await client.open_session(
                    principal_id=str(fixture.principal_id),
                )
                sid = session["session_id"]
                mission = await client.read_mission(
                    session_id=sid,
                    principal_id=str(fixture.principal_id),
                    mission_id=mission_id,
                )
                control = await client.read_mission_control(
                    session_id=sid,
                    principal_id=str(fixture.principal_id),
                    mission_id=mission_id,
                )
                views[label] = (mission, control)

            cli_mission, cli_control = views["cli"]
            for label in CLIENTS:
                mission, control = views[label]
                assert _mission_slice(mission) == _mission_slice(cli_mission), label
                assert _control_slice(control) == _control_slice(cli_control), label
                assert mission["slug"] == slug
                assert mission["status"] == "CREATED"
                assert control["mission_id"] == mission_id

            # Activate via Gateway control (CREATED → ACTIVE), then pause.
            web = GatewayClient(http)
            web_session = await web.open_session(
                principal_id=str(fixture.principal_id),
            )
            current = await web.read_mission(
                session_id=web_session["session_id"],
                principal_id=str(fixture.principal_id),
                mission_id=mission_id,
            )
            activate_status, activate_body = await web.accept_command(
                session_id=web_session["session_id"],
                principal_id=str(fixture.principal_id),
                command_type="mission.resume",
                target_type="mission",
                target_id=mission_id,
                parameters={"lock_version": current["lock_version"]},
                idempotency_key=f"parity-activate-{uuid7().hex[:8]}",
            )
            assert activate_status == 202, activate_body

            active = await web.read_mission(
                session_id=web_session["session_id"],
                principal_id=str(fixture.principal_id),
                mission_id=mission_id,
            )
            assert active["status"] == "ACTIVE"
            pause_key = f"parity-pause-{uuid7().hex[:8]}"
            pause_status, pause_body = await web.accept_command(
                session_id=web_session["session_id"],
                principal_id=str(fixture.principal_id),
                command_type="mission.pause",
                target_type="mission",
                target_id=mission_id,
                parameters={"lock_version": active["lock_version"]},
                idempotency_key=pause_key,
            )
            assert pause_status == 202, pause_body

            after: dict[str, str] = {}
            for label in CLIENTS:
                client = GatewayClient(http)
                session = await client.open_session(
                    principal_id=str(fixture.principal_id),
                )
                mission = await client.read_mission(
                    session_id=session["session_id"],
                    principal_id=str(fixture.principal_id),
                    mission_id=mission_id,
                )
                after[label] = mission["status"]
            assert after["cli"] == after["web"] == after["android"] == "PAUSED"
    finally:
        app.state.engine = None
        await engine.dispose()


@pytest.mark.asyncio
async def test_reconnect_does_not_duplicate_commands() -> None:
    """Ch.15.1 subset: resume + by-id; same idempotency key → one mutation."""
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
        ) as http:
            client = GatewayClient(http)
            opened = await client.open_session(
                principal_id=str(fixture.principal_id),
            )
            session_id = opened["session_id"]
            create_status, created = await client.accept_command(
                session_id=session_id,
                principal_id=str(fixture.principal_id),
                command_type="mission.create",
                target_type="project",
                target_id=str(fixture.project_id),
                parameters={
                    "slug": f"MISSION-PARITY-RC-{uuid7().hex[:8]}",
                    "title": "Reconnect parity",
                    "intent": "No duplicate commands on reconnect",
                    "success_definition": "Idempotent pause replay",
                    "scope": ["engine"],
                    "requirement_refs": [],
                    "autonomy_ceiling": 1,
                },
                idempotency_key=f"parity-rc-create-{uuid7().hex[:8]}",
            )
            assert create_status == 202, created
            mission_id = created["target_id"]

            before = await client.read_mission(
                session_id=session_id,
                principal_id=str(fixture.principal_id),
                mission_id=mission_id,
            )
            activate_status, activate_body = await client.accept_command(
                session_id=session_id,
                principal_id=str(fixture.principal_id),
                command_type="mission.resume",
                target_type="mission",
                target_id=mission_id,
                parameters={"lock_version": before["lock_version"]},
                idempotency_key=f"parity-rc-activate-{uuid7().hex[:8]}",
            )
            assert activate_status == 202, activate_body
            active = await client.read_mission(
                session_id=session_id,
                principal_id=str(fixture.principal_id),
                mission_id=mission_id,
            )
            assert active["status"] == "ACTIVE"

            pause_key = f"parity-rc-pause-{uuid7().hex[:8]}"
            command_id = str(uuid7())
            first_status, first = await client.accept_command(
                session_id=session_id,
                principal_id=str(fixture.principal_id),
                command_type="mission.pause",
                target_type="mission",
                target_id=mission_id,
                parameters={"lock_version": active["lock_version"]},
                idempotency_key=pause_key,
                command_id=command_id,
            )
            assert first_status == 202, first

            # Android ReconnectCoordinator pattern: resume then by-id re-sync.
            cursor = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
            resumed = await client.resume_session(session_id, last_event_at=cursor)
            assert "session" in resumed
            assert "fresh_snapshot" in resumed
            mission = await client.read_mission(
                session_id=session_id,
                principal_id=str(fixture.principal_id),
                mission_id=mission_id,
            )
            control = await client.read_mission_control(
                session_id=session_id,
                principal_id=str(fixture.principal_id),
                mission_id=mission_id,
            )
            assert mission["status"] == "PAUSED"
            assert control["mission_id"] == mission_id

            # Replayed mutation with the same key must not create a second effect.
            replay_status, replay = await client.accept_command(
                session_id=session_id,
                principal_id=str(fixture.principal_id),
                command_type="mission.pause",
                target_type="mission",
                target_id=mission_id,
                parameters={"lock_version": active["lock_version"]},
                idempotency_key=pause_key,
                command_id=command_id,
            )
            assert replay_status == 202, replay
            assert replay["command_id"] == first["command_id"]
            assert replay["target_id"] == first["target_id"]

            after = await client.read_mission(
                session_id=session_id,
                principal_id=str(fixture.principal_id),
                mission_id=mission_id,
            )
            assert after["status"] == "PAUSED"
            assert after["lock_version"] == mission["lock_version"]
    finally:
        app.state.engine = None
        await engine.dispose()
