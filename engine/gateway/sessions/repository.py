"""Async repositories for the gateway session surface (Chapter 15.1, 13.9).

Every read and write here executes on the connection of an already-open unit
of work (Chapter 3.5); this module never begins or ends a transaction itself.
"""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.client_session import ClientSession
from engine.gateway.sessions.tables import (
    client_sessions,
    principal_grants,
    principals,
)

_JSONB_FIELDS = ("scopes", "subscriptions")


def _json_safe(value: object) -> object:
    if isinstance(value, (list, dict)):
        return json.loads(json.dumps(value, default=str))
    return value


class ClientSessionRepository:
    """Reads and writes rows for the `client_sessions` table."""

    async def insert(self, connection: AsyncConnection, record: ClientSession) -> None:
        dumped = record.model_dump()
        for field in _JSONB_FIELDS:
            dumped[field] = _json_safe(dumped[field])
        await connection.execute(client_sessions.insert().values(**dumped))

    async def get_by_id(
        self, connection: AsyncConnection, session_id: UUID
    ) -> ClientSession | None:
        result = await connection.execute(
            select(client_sessions).where(client_sessions.c.session_id == session_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return ClientSession.model_validate(dict(row))

    async def update_fields(
        self,
        connection: AsyncConnection,
        session_id: UUID,
        *,
        fields: dict[str, object],
    ) -> int:
        safe = {name: _json_safe(value) for name, value in fields.items()}
        result = await connection.execute(
            client_sessions.update()
            .where(client_sessions.c.session_id == session_id)
            .values(**safe)
        )
        return int(result.rowcount)


class PrincipalLookup:
    """Read-only identity resolution (Chapter 13.9, 14.2).

    `principals` and `principal_grants` are written by the tenancy authority
    layer (DDE-051); the gateway only reads them to resolve the authenticated
    principal's tenant and to check project membership.
    """

    async def tenant_for_principal(
        self, connection: AsyncConnection, principal_id: UUID
    ) -> UUID | None:
        result = await connection.execute(
            select(principals.c.tenant_id).where(
                principals.c.principal_id == principal_id
            )
        )
        row = result.first()
        return row[0] if row is not None else None

    async def grant_covers(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        principal_id: UUID,
        project_id: UUID,
    ) -> bool:
        """True when the principal holds a tenant-wide grant (`project_id`
        NULL) or a grant for exactly `project_id` under `tenant_id`."""
        result = await connection.execute(
            select(principal_grants.c.project_id).where(
                principal_grants.c.tenant_id == tenant_id,
                principal_grants.c.principal_id == principal_id,
            )
        )
        for row in result.all():
            granted = row[0]
            if granted is None or granted == project_id:
                return True
        return False
