"""Gateway session service — ClientSession lifecycle and reconnect (Chapter 15.1).

The gateway derives tenant identity from the authenticated principal and
never from a client-supplied target id (Chapter 13.9). `principals` and
`principal_grants` are read here to resolve that identity; they are written
by the tenancy authority layer (DDE-051), not this module.

Identity reads run on a connection without a tenant GUC because the tenant is
exactly what is being resolved. The local dev `dde` role is a superuser and
therefore bypasses RLS (see `tests/support/db.py`); a dedicated non-bypass
identity role is DDE-051's production hardening. Tenant-scoped writes (the
session row itself) go through `open_unit_of_work` with the derived tenant
GUC so they remain fail-closed under RLS.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from engine.contracts.client_session import ClientSession
from engine.contracts.event import Event
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.tables import events
from engine.gateway.scopes import BASELINE_SCOPES
from engine.gateway.sessions.repository import (
    ClientSessionRepository,
    PrincipalLookup,
)
from engine.gateway.sessions.states import transition
from engine.truth.db import open_unit_of_work


class GatewaySessionService:
    """Async, PostgreSQL-backed writer for `client_sessions` plus the
    gateway's identity resolution and reconnect reads (Chapter 15.1)."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: ClientSessionRepository | None = None,
        principals: PrincipalLookup | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or ClientSessionRepository()
        self._principals = principals or PrincipalLookup()
        self._clock = clock or SystemClock()

    @asynccontextmanager
    async def _identity(self) -> AsyncIterator[AsyncConnection]:
        """One connection without a tenant GUC, for identity resolution that
        must run before tenant scope is known (Chapter 13.9)."""
        async with self._engine.connect() as connection:
            yield connection

    async def open_session(
        self,
        *,
        principal_id: UUID,
        client_type: str,
        device_id: UUID | None = None,
        protocol_version: str = "1",
        scopes: list[str],
        subscriptions: list[str],
    ) -> ClientSession:
        """Open a session for an authenticated principal (Chapter 15.1).

        The requested scopes must be a subset of the principal class's
        baseline scopes (Chapter 14.2); the tenant is derived from the
        principal, never supplied by the client (Chapter 13.9).
        """
        baseline = BASELINE_SCOPES.get(client_type)
        if baseline is None:
            raise DdeError(
                "FORBIDDEN",
                "Unknown client_type",
                details={"client_type": client_type},
            )
        if not set(scopes).issubset(baseline):
            raise DdeError(
                "FORBIDDEN",
                "Scope not granted for client_type",
                details={"client_type": client_type, "scopes": scopes},
            )
        # Ch.14.2 device principal is device-bound: a device session without
        # device_id cannot be authorized for device.command / device.read.
        if client_type == "device" and device_id is None:
            raise DdeError(
                "FORBIDDEN",
                "device_id is required for client_type=device",
                details={"client_type": client_type},
            )
        async with self._identity() as connection:
            tenant_id = await self._principals.tenant_for_principal(
                connection, principal_id
            )
        if tenant_id is None:
            raise DdeError(
                "INVALID_CREDENTIALS",
                "Unknown principal",
                details={"principal_id": str(principal_id)},
            )
        now = self._clock.now()
        session = ClientSession(
            session_id=uuid7(),
            tenant_id=tenant_id,
            principal_id=principal_id,
            client_type=client_type,
            device_id=device_id,
            protocol_version=protocol_version,
            scopes=scopes,
            connected_at=now,
            last_seen_at=now,
            subscriptions=subscriptions,
            status="ACTIVE",
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(self._engine, tenant_id=tenant_id) as uow:
            await self._repository.insert(uow.connection, session)
            await uow.commit()
        return session

    async def authorize_scope(
        self,
        *,
        session_id: UUID,
        principal_id: UUID,
        required_scope: str,
    ) -> ClientSession:
        """Authorize a command against the session (Chapter 15.1: "authorize
        command scope before it reaches Core"). Fails closed on an unknown,
        closed or expired session, on a principal mismatch, or on a scope the
        session was never granted."""
        session = await self._require_active_session(session_id)
        if session.principal_id != principal_id:
            raise DdeError(
                "FORBIDDEN",
                "Session principal mismatch",
                details={"session_id": str(session_id)},
            )
        if required_scope not in session.scopes:
            raise DdeError(
                "FORBIDDEN",
                "Scope not granted to session",
                details={"required_scope": required_scope, "scopes": session.scopes},
            )
        await self._touch(session)
        return session

    async def authorize_project(self, session: ClientSession, project_id: UUID) -> None:
        """Verify the principal is authorized for the target project before a
        project-scoped command reaches Core (Chapter 13.9: a principal must be
        authorized for the tenant and project before any domain operation)."""
        async with self._identity() as connection:
            granted = await self._principals.grant_covers(
                connection,
                tenant_id=session.tenant_id,
                principal_id=session.principal_id,
                project_id=project_id,
            )
        if not granted:
            raise DdeError(
                "TENANT_SCOPE_VIOLATION",
                "Principal is not authorized for the target project",
                details={"project_id": str(project_id)},
            )

    async def resume(
        self, *, session_id: UUID, last_event_at: datetime | None = None
    ) -> tuple[ClientSession, list[Event], bool]:
        """Reconnect semantics (Chapter 15.1).

        A reconnecting client presents its session id and last acknowledged
        event cursor. With no cursor the client gets a fresh snapshot (no
        events). With a cursor it receives retained events for its subscribed
        aggregates occurring after that cursor; if a bounded gap cannot be
        replayed, the caller is told to re-sync via a fresh snapshot.
        """
        session = await self._require_active_session(session_id)
        if last_event_at is None:
            await self._touch(session)
            return session, [], True
        retained = await self._retained_events(session, last_event_at)
        await self._touch(session)
        return session, retained, False

    async def close_session(self, *, session_id: UUID) -> ClientSession:
        session = await self._require_active_session(session_id)
        now = self._clock.now()
        async with open_unit_of_work(self._engine, tenant_id=session.tenant_id) as uow:
            await self._repository.update_fields(
                uow.connection,
                session.session_id,
                fields={
                    "status": transition(session.status, "CLOSED"),
                    "updated_at": now,
                },
            )
            await uow.commit()
        closed = await self._get_session(session_id)
        if closed is None:
            raise DdeError(
                "SESSION_EXPIRED",
                "Unknown session",
                details={"session_id": str(session_id)},
            )
        return closed

    async def _require_active_session(self, session_id: UUID) -> ClientSession:
        session = await self._get_session(session_id)
        if session is None:
            raise DdeError(
                "SESSION_EXPIRED",
                "Unknown session",
                details={"session_id": str(session_id)},
            )
        if session.status != "ACTIVE":
            raise DdeError(
                "SESSION_EXPIRED",
                f"Session is {session.status}",
                details={"session_id": str(session_id), "status": session.status},
            )
        return session

    async def _get_session(self, session_id: UUID) -> ClientSession | None:
        async with self._identity() as connection:
            return await self._repository.get_by_id(connection, session_id)

    async def _touch(self, session: ClientSession) -> None:
        now = self._clock.now()
        async with open_unit_of_work(self._engine, tenant_id=session.tenant_id) as uow:
            await self._repository.update_fields(
                uow.connection,
                session.session_id,
                fields={"last_seen_at": now, "updated_at": now},
            )
            await uow.commit()

    async def _retained_events(
        self, session: ClientSession, after: datetime
    ) -> list[Event]:
        if not session.subscriptions:
            return []
        async with self._identity() as connection:
            result = await connection.execute(
                select(events)
                .where(
                    events.c.tenant_id == session.tenant_id,
                    events.c.aggregate_type.in_(session.subscriptions),
                    events.c.occurred_at > after,
                )
                .order_by(events.c.occurred_at.asc())
            )
            return [Event.model_validate(dict(row)) for row in result.mappings().all()]
