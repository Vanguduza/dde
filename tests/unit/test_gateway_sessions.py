"""PostgreSQL-backed gateway session lifecycle + reconnect (DDE-027, Ch.15.1)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import text

from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.gateway.sessions.service import GatewaySessionService
from engine.missions.service import MissionService
from tests.support.db import new_engine, seed_tenant


async def _seed_grant(
    engine, *, tenant_id: UUID, principal_id: UUID, project_id: UUID
) -> None:
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


@pytest.mark.asyncio
async def test_open_session_derives_tenant_from_principal() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = GatewaySessionService(engine)
        session = await service.open_session(
            principal_id=fixture.principal_id,
            client_type="human",
            scopes=["mission.read"],
            subscriptions=["mission"],
        )
        assert session.tenant_id == fixture.tenant_id
        assert session.principal_id == fixture.principal_id
        assert session.status == "ACTIVE"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_open_session_rejects_scope_outside_baseline() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = GatewaySessionService(engine)
        with pytest.raises(DdeError) as captured:
            await service.open_session(
                principal_id=fixture.principal_id,
                client_type="human",
                scopes=["worker.execute"],
                subscriptions=[],
            )
        assert captured.value.error_code == "FORBIDDEN"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_open_session_rejects_unknown_principal() -> None:
    engine = new_engine()
    try:
        service = GatewaySessionService(engine)
        with pytest.raises(DdeError) as captured:
            await service.open_session(
                principal_id=uuid7(),
                client_type="human",
                scopes=["mission.read"],
                subscriptions=[],
            )
        assert captured.value.error_code == "INVALID_CREDENTIALS"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_authorize_scope_requires_granted_scope() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = GatewaySessionService(engine)
        session = await service.open_session(
            principal_id=fixture.principal_id,
            client_type="human",
            scopes=["mission.read"],
            subscriptions=[],
        )
        with pytest.raises(DdeError) as captured:
            await service.authorize_scope(
                session_id=session.session_id,
                principal_id=fixture.principal_id,
                required_scope="mission.control",
            )
        assert captured.value.error_code == "FORBIDDEN"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_authorize_scope_rejects_principal_mismatch() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = GatewaySessionService(engine)
        session = await service.open_session(
            principal_id=fixture.principal_id,
            client_type="human",
            scopes=["mission.read"],
            subscriptions=[],
        )
        with pytest.raises(DdeError) as captured:
            await service.authorize_scope(
                session_id=session.session_id,
                principal_id=uuid7(),
                required_scope="mission.read",
            )
        assert captured.value.error_code == "FORBIDDEN"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_closed_session_cannot_authorize() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = GatewaySessionService(engine)
        session = await service.open_session(
            principal_id=fixture.principal_id,
            client_type="human",
            scopes=["mission.read"],
            subscriptions=[],
        )
        closed = await service.close_session(session_id=session.session_id)
        assert closed.status == "CLOSED"
        with pytest.raises(DdeError) as captured:
            await service.authorize_scope(
                session_id=session.session_id,
                principal_id=fixture.principal_id,
                required_scope="mission.read",
            )
        assert captured.value.error_code == "SESSION_EXPIRED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_resume_fresh_snapshot_without_cursor() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = GatewaySessionService(engine)
        session = await service.open_session(
            principal_id=fixture.principal_id,
            client_type="human",
            scopes=["mission.read"],
            subscriptions=["mission"],
        )
        _resumed, retained, fresh = await service.resume(session_id=session.session_id)
        assert fresh is True
        assert retained == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_resume_returns_retained_events_after_cursor() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = GatewaySessionService(engine)
        session = await service.open_session(
            principal_id=fixture.principal_id,
            client_type="human",
            scopes=["mission.read"],
            subscriptions=["mission"],
        )
        before = datetime.now(UTC) - timedelta(seconds=1)
        await MissionService(engine, EventService(engine)).create_mission(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            slug=f"MISSION-SESSION-{uuid7().hex[:12]}",
            title="Reconnect fixture",
            intent="Emit a mission event",
            success_definition="Event retained",
            scope=["engine"],
            requirement_refs=[],
            autonomy_ceiling=1,
        )
        _resumed, retained, fresh = await service.resume(
            session_id=session.session_id, last_event_at=before
        )
        assert fresh is False
        assert any(event.event_type == "MissionCommitted" for event in retained)

        after = datetime.now(UTC) + timedelta(seconds=1)
        _resumed, retained_after, _fresh = await service.resume(
            session_id=session.session_id, last_event_at=after
        )
        assert retained_after == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_authorize_project_requires_grant() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = GatewaySessionService(engine)
        session = await service.open_session(
            principal_id=fixture.principal_id,
            client_type="human",
            scopes=["mission.create"],
            subscriptions=[],
        )
        with pytest.raises(DdeError) as captured:
            await service.authorize_project(session, fixture.project_id)
        assert captured.value.error_code == "TENANT_SCOPE_VIOLATION"

        await _seed_grant(
            engine,
            tenant_id=fixture.tenant_id,
            principal_id=fixture.principal_id,
            project_id=fixture.project_id,
        )
        await service.authorize_project(session, fixture.project_id)
    finally:
        await engine.dispose()
