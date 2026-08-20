"""Async repository for the `audit_events` table (Chapter 3.3, 3.7).

Every read and write here executes on the connection of an already-open unit
of work (Chapter 3.5); this module never begins or ends a transaction
itself.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.audit.tables import audit_events
from engine.contracts.audit_event import AuditEvent


class AuditRepository:
    """Reads and writes rows for the hash-chained `audit_events` table."""

    async def get_latest(
        self, connection: AsyncConnection, tenant_id: UUID
    ) -> AuditEvent | None:
        result = await connection.execute(
            select(audit_events)
            .where(audit_events.c.tenant_id == tenant_id)
            .order_by(audit_events.c.sequence.desc())
            .limit(1)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return AuditEvent.model_validate(dict(row))

    async def list_for_tenant(
        self, connection: AsyncConnection, tenant_id: UUID
    ) -> list[AuditEvent]:
        result = await connection.execute(
            select(audit_events)
            .where(audit_events.c.tenant_id == tenant_id)
            .order_by(audit_events.c.sequence.asc())
        )
        return [AuditEvent.model_validate(dict(row)) for row in result.mappings().all()]

    async def insert(self, connection: AsyncConnection, record: AuditEvent) -> None:
        await connection.execute(audit_events.insert().values(**record.model_dump()))
