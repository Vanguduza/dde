"""DDE-053 Android client: Gateway reconnect proofs (Ch.15.1 subset Core has).

These tests pin the reconnect behaviour the Kotlin client must implement:
resume with a cursor, then by-id re-sync when a fresh snapshot is required.
They do not claim WS/SSE or sequence-based replay (EDR-0027).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from engine.core.ids import uuid7
from interfaces.api import app
from tests.support.db import new_engine, seed_tenant

ROOT = Path(__file__).resolve().parents[2]
ANDROID = ROOT / "interfaces" / "android"
DASHBOARD_GATEWAY = (
    ROOT / "interfaces" / "dashboard" / "static" / "gateway.js"
)


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


def _command_body(**kwargs) -> dict:
    return {
        "command_id": str(uuid7()),
        "idempotency_key": kwargs["key"],
        "principal_id": str(kwargs["principal_id"]),
        "client_session_id": str(kwargs["session_id"]),
        "target_type": kwargs["target_type"],
        "target_id": str(kwargs["target_id"]),
        "command_type": kwargs["command_type"],
        "parameters": kwargs["parameters"],
        "requested_at": datetime.now(UTC).isoformat(),
        "protocol_version": "1",
    }


def test_android_never_imports_engine() -> None:
    banned = ("from engine.", "import engine", "sqlalchemy", "asyncpg")
    offenders: list[str] = []
    for path in ANDROID.rglob("*"):
        if path.suffix.lower() not in {".kt", ".kts", ".md", ".py"}:
            continue
        text = path.read_text(encoding="utf-8").lower()
        if any(token in text for token in banned):
            # README may mention engine/** as a forbidden import — allow
            # prose that says "never".
            if path.name == "README.md" and "never" in text:
                continue
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_android_package_scaffolded() -> None:
    assert (ANDROID / "README.md").is_file()
    assert (ANDROID / "app" / "src" / "main" / "kotlin").is_dir() or (
        ANDROID / "app" / "src" / "main" / "java"
    ).is_dir() or (ANDROID / "gateway").is_dir()


def test_android_allowlist_matches_dashboard_gateway_js() -> None:
    """API parity with DDE-052: same six /v1 operations, no invented lists."""
    source = DASHBOARD_GATEWAY.read_text(encoding="utf-8")
    for marker in (
        "POST /v1/sessions",
        "POST /v1/sessions/{id}/resume",
        "POST /v1/sessions/{id}/close",
        "POST /v1/commands",
        "GET /v1/missions/{id}",
        "GET /v1/mission-control/{id}",
    ):
        assert marker in source
    # Kotlin client must document the same allowlist.
    kotlin_roots = list(ANDROID.rglob("*.kt"))
    assert kotlin_roots, "expected Kotlin sources under interfaces/android"
    joined = "\n".join(path.read_text(encoding="utf-8") for path in kotlin_roots)
    assert "ALLOWED_PATHS" in joined or "allowlist" in joined.lower()
    assert "/v1/missions/{id}" in joined or "missions/" in joined
    assert "resume" in joined.lower()


@pytest.mark.asyncio
async def test_reconnect_resume_then_by_id_resync() -> None:
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
            session_id = session["session_id"]

            created = await client.post(
                "/v1/commands",
                json=_command_body(
                    key=f"android-create-{uuid7().hex[:8]}",
                    session_id=session_id,
                    principal_id=fixture.principal_id,
                    target_type="project",
                    target_id=fixture.project_id,
                    command_type="mission.create",
                    parameters={
                        "slug": f"MISSION-AND-{uuid7().hex[:8]}",
                        "title": "Android reconnect fixture",
                        "intent": "Prove resume + by-id re-sync",
                        "success_definition": "Readable after resume",
                        "scope": ["engine"],
                        "requirement_refs": [],
                        "autonomy_ceiling": 1,
                    },
                ),
            )
            assert created.status_code == 202
            mission_id = created.json()["target_id"]
            headers = {
                "X-Session-Id": session_id,
                "X-Principal-Id": str(fixture.principal_id),
            }
            before = await client.get(f"/v1/missions/{mission_id}", headers=headers)
            assert before.status_code == 200

            # Client reconnect: resume with a cursor in the past, then
            # always re-GET by id (Android must not trust stale local UI).
            cursor = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
            resumed = await client.post(
                f"/v1/sessions/{session_id}/resume",
                json={"last_event_at": cursor},
            )
            assert resumed.status_code == 200
            body = resumed.json()
            assert "session" in body
            assert "fresh_snapshot" in body
            assert "events" in body

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
async def test_android_path_rejects_cross_tenant_after_resume() -> None:
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
                    key=f"android-x-{uuid7().hex[:8]}",
                    session_id=owner_session["session_id"],
                    principal_id=owner.principal_id,
                    target_type="project",
                    target_id=owner.project_id,
                    command_type="mission.create",
                    parameters={
                        "slug": f"MISSION-AX-{uuid7().hex[:8]}",
                        "title": "Cross-tenant fixture",
                        "intent": "Authz",
                        "success_definition": "Denied to stranger",
                        "scope": ["engine"],
                        "requirement_refs": [],
                        "autonomy_ceiling": 1,
                    },
                ),
            )
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
            await client.post(
                f"/v1/sessions/{stranger_session['session_id']}/resume",
                json={"last_event_at": None},
            )
            denied = await client.get(
                f"/v1/missions/{mission_id}",
                headers={
                    "X-Session-Id": stranger_session["session_id"],
                    "X-Principal-Id": str(stranger.principal_id),
                },
            )
            assert denied.status_code in {403, 404}
    finally:
        app.state.engine = None
        await engine.dispose()
