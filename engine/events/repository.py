"""Async repository for the `events` and `outbox` tables (Chapter 3.3, 3.7).

Every read and write here executes on the connection of an already-open unit
of work (Chapter 3.5); this module never begins or ends a transaction
itself.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.event import Event
from engine.contracts.outbox import Outbox
from engine.events.tables import events, outbox


class EventsRepository:
    """Reads and writes rows for the append-only `events` table and its
    transactional `outbox` companion."""

    async def next_sequence(
        self, connection: AsyncConnection, aggregate_type: str, aggregate_id: UUID
    ) -> int:
        """Per-aggregate sequence (Chapter 16.3: per-aggregate ordering is
        guaranteed; global ordering is not, so this only needs to be
        monotonic within one `(aggregate_type, aggregate_id)` pair)."""
        result = await connection.execute(
            select(func.coalesce(func.max(events.c.sequence), 0)).where(
                events.c.aggregate_type == aggregate_type,
                events.c.aggregate_id == aggregate_id,
            )
        )
        return int(result.scalar_one()) + 1

    async def insert_event(self, connection: AsyncConnection, record: Event) -> None:
        await connection.execute(events.insert().values(**record.model_dump()))

    async def get_event(
        self, connection: AsyncConnection, event_id: UUID
    ) -> Event | None:
        result = await connection.execute(
            select(events).where(events.c.event_id == event_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return Event.model_validate(dict(row))

    async def list_events_for_aggregate(
        self, connection: AsyncConnection, aggregate_type: str, aggregate_id: UUID
    ) -> list[Event]:
        result = await connection.execute(
            select(events)
            .where(
                events.c.aggregate_type == aggregate_type,
                events.c.aggregate_id == aggregate_id,
            )
            .order_by(events.c.sequence.asc())
        )
        return [Event.model_validate(dict(row)) for row in result.mappings().all()]

    async def insert_outbox(self, connection: AsyncConnection, record: Outbox) -> None:
        await connection.execute(outbox.insert().values(**record.model_dump()))

    async def get_outbox(
        self, connection: AsyncConnection, outbox_id: UUID
    ) -> Outbox | None:
        result = await connection.execute(
            select(outbox).where(outbox.c.outbox_id == outbox_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return Outbox.model_validate(dict(row))

    async def claim_pending_for_dispatch(
        self, connection: AsyncConnection, *, limit: int
    ) -> list[Outbox]:
        """`SELECT ... FOR UPDATE SKIP LOCKED` (Chapter 3.5): rows already
        locked by a concurrent dispatcher instance are skipped rather than
        awaited, so N dispatcher instances can drain the same outbox without
        ever claiming the same row (Chapter 17.1)."""
        result = await connection.execute(
            select(outbox)
            .where(outbox.c.status == "pending")
            .order_by(outbox.c.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return [Outbox.model_validate(dict(row)) for row in result.mappings().all()]

    async def mark_published(
        self,
        connection: AsyncConnection,
        outbox_id: UUID,
        *,
        published_at: datetime,
    ) -> None:
        await connection.execute(
            outbox.update()
            .where(outbox.c.outbox_id == outbox_id)
            .values(
                status="published",
                published_at=published_at,
                updated_at=published_at,
            )
        )
