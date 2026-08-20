"""Event store, transactional outbox and command ledger."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import timedelta
from uuid import UUID

from engine.contracts.command_idempotency import CommandIdempotency
from engine.contracts.event import Event
from engine.contracts.outbox import Outbox
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7

Publisher = Callable[[Event], Awaitable[None]]


@dataclass
class EventStore:
    events: list[Event] = field(default_factory=list)
    outbox: dict[UUID, Outbox] = field(default_factory=dict)
    commands: dict[tuple[UUID, str], CommandIdempotency] = field(default_factory=dict)
    sequences: dict[tuple[str, UUID], int] = field(default_factory=dict)

    def unpublished(self) -> list[Outbox]:
        return [row for row in self.outbox.values() if row.status == "pending"]


class EventEngine:
    """Append-only events committed with outbox rows in one unit of work."""

    def __init__(self, store: EventStore, clock: Clock | None = None) -> None:
        self._store = store
        self._clock = clock or SystemClock()

    def append(
        self,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: UUID,
        tenant_id: UUID,
        project_id: UUID,
        payload: dict[str, object],
        mission_id: UUID | None = None,
        task_id: UUID | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> Event:
        now = self._clock.now()
        key = (aggregate_type, aggregate_id)
        sequence = self._store.sequences.get(key, 0) + 1
        self._store.sequences[key] = sequence
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
            schema_version="1",
            created_at=now,
            updated_at=now,
        )
        outbox = Outbox(
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
        self._store.events.append(event)
        self._store.outbox[outbox.outbox_id] = outbox
        return event

    def claim_pending(self, limit: int = 16) -> list[Outbox]:
        pending = sorted(self._store.unpublished(), key=lambda row: row.created_at)
        return pending[:limit]

    def mark_published(self, outbox_id: UUID) -> Outbox:
        row = self._store.outbox[outbox_id]
        now = self._clock.now()
        updated = row.model_copy(
            update={"status": "published", "published_at": now, "updated_at": now}
        )
        self._store.outbox[outbox_id] = updated
        return updated

    async def dispatch(self, publish: Publisher, *, limit: int = 16) -> int:
        claimed = self.claim_pending(limit=limit)
        for row in claimed:
            event = Event.model_validate(row.payload)
            await publish(event)
            self.mark_published(row.outbox_id)
        return len(claimed)

    def accept_command(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        idempotency_key: str,
        request_hash: str,
        ttl: timedelta | None = None,
    ) -> tuple[CommandIdempotency, bool]:
        key = (tenant_id, idempotency_key)
        existing = self._store.commands.get(key)
        now = self._clock.now()
        if existing is not None:
            if existing.expires_at <= now:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Idempotency key expired; refusing mutation that could duplicate",
                    details={"idempotency_key": idempotency_key},
                )
            if existing.request_hash != request_hash:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Idempotency key reused with a different request hash",
                )
            return existing, False
        window = ttl or timedelta(days=30)
        record = CommandIdempotency(
            command_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status="first_seen",
            result=None,
            expires_at=now + window,
            created_at=now,
            updated_at=now,
        )
        self._store.commands[key] = record
        return record, True
