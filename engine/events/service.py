"""Production event store — the sole writer of `events`/`outbox` rows in
PostgreSQL (Chapter 3.8: "Event ... Owning aggregate transaction ...
Outbox").

Unlike the in-memory `EventEngine` test double in `engine.events.engine`,
this service persists the event and its outbox row durably, in the same
transaction as the caller's domain write, matching
`engine.truth.service.TruthService` and `engine.audit.service.AuditService`'s
production pattern (Chapter 3.5: a transaction may span module boundaries,
so a caller composing a cross-module transaction — e.g. `engine.governance`
recording a decision alongside its event — can pass an already-open unit of
work).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.event import Event
from engine.contracts.outbox import Outbox
from engine.core.clock import Clock, SystemClock
from engine.core.ids import uuid7
from engine.events.repository import EventsRepository
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")

SCHEMA_VERSION = "1"


class EventService:
    """Async, PostgreSQL-backed writer for the `events` event store and its
    `outbox` companion row. Each public method opens and commits its own
    unit of work unless one is supplied, so a caller composing a
    cross-module transaction can share it instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: EventsRepository | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or EventsRepository()
        self._clock = clock or SystemClock()

    async def _run(
        self,
        uow: PostgresUnitOfWork | None,
        tenant_id: UUID,
        project_id: UUID,
        body: Callable[[PostgresUnitOfWork], Awaitable[T]],
    ) -> T:
        if uow is not None:
            return await body(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as owned:
            result = await body(owned)
            await owned.commit()
            return result

    async def append(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        event_type: str,
        aggregate_type: str,
        aggregate_id: UUID,
        payload: dict[str, object],
        mission_id: UUID | None = None,
        task_id: UUID | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> Event:
        """Append one event and its pending outbox row in the same
        transaction (Chapter 3.9's "Event ... Owning aggregate transaction
        ... Outbox" rule). Never commits a domain write's event without the
        domain write itself, or vice versa — callers must pass their own
        open `uow` to get that guarantee."""

        async def _op(active: PostgresUnitOfWork) -> Event:
            now = self._clock.now()
            sequence = await self._repository.next_sequence(
                active.connection, aggregate_type, aggregate_id
            )
            event = Event(
                event_id=uuid7(),
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                task_id=task_id,
                sequence=sequence,
                occurred_at=now,
                correlation_id=correlation_id or str(uuid7()),
                causation_id=causation_id,
                payload=payload,
                schema_version=SCHEMA_VERSION,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_event(active.connection, event)
            outbox_row = Outbox(
                outbox_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                event_id=event.event_id,
                status="pending",
                payload=event.model_dump(mode="json"),
                published_at=None,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_outbox(active.connection, outbox_row)
            return event

        return await self._run(uow, tenant_id, project_id, _op)
