"""Read-only repository for the Mission Control projection (Chapter 3.6, 15.4).

Every read here executes on the connection of an already-open unit of work
(Chapter 3.5); this module never begins or ends a transaction itself. It is a
read model — it owns no tables and writes no rows.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.events.tables import events


class MissionControlRepository:
    """Reads the durable rows the Mission Control projection aggregates."""

    async def latest_event_cursor(
        self, connection: AsyncConnection, mission_id: UUID
    ) -> datetime | None:
        """Most recent `occurred_at` for a mission's events, or `None`.

        This is the reconnect cursor a client replays from (Chapter 15.1).
        """
        result = await connection.execute(
            select(func.max(events.c.occurred_at)).where(
                events.c.mission_id == mission_id
            )
        )
        value = result.scalar()
        return value if isinstance(value, datetime) else None
