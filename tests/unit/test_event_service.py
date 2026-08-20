"""Production event store, outbox dispatcher and command ledger against
real PostgreSQL (Chapter 3.3, 3.5, 3.7, 3.9, 16.3, 19.1).
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from engine.contracts.event import Event
from engine.core.errors import DdeError
from engine.core.hashing import sha256_hex
from engine.core.ids import uuid7
from engine.events.dispatcher import OutboxDispatcher
from engine.events.idempotency import COMMAND_IDEMPOTENCY_RETENTION_V1, CommandLedger
from engine.events.repository import EventsRepository
from engine.events.service import EventService
from engine.events.tables import outbox
from engine.truth.db import open_unit_of_work
from tests.support.db import new_engine, seed_tenant, truncate_outbox


@pytest.mark.asyncio
async def test_append_writes_event_and_pending_outbox_row_in_one_transaction() -> None:
    """The state-transition test: a single `append()` call durably creates
    both an `events` row and its `outbox` companion, status `pending`."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = EventService(engine)
        aggregate_id = uuid7()

        event = await service.append(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            event_type="MissionCommitted",
            aggregate_type="mission",
            aggregate_id=aggregate_id,
            payload={"slug": "MISSION-ERP-000421"},
        )
        assert event.sequence == 1

        async with open_unit_of_work(
            engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            stored_event = await EventsRepository().get_event(
                uow.connection, event.event_id
            )
            outbox_result = await uow.connection.execute(
                select(outbox).where(outbox.c.event_id == event.event_id)
            )
            outbox_row = outbox_result.mappings().first()
            await uow.commit()
        assert stored_event is not None
        assert stored_event.payload == {"slug": "MISSION-ERP-000421"}
        assert outbox_row is not None
        assert outbox_row["status"] == "pending"
        assert outbox_row["published_at"] is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_sequence_is_monotonic_per_aggregate() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = EventService(engine)
        aggregate_id = uuid7()

        first = await service.append(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            event_type="TaskTransitioned",
            aggregate_type="task",
            aggregate_id=aggregate_id,
            payload={"to": "READY"},
        )
        second = await service.append(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            event_type="TaskTransitioned",
            aggregate_type="task",
            aggregate_id=aggregate_id,
            payload={"to": "COMPLETED"},
        )
        other_aggregate = await service.append(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            event_type="TaskTransitioned",
            aggregate_type="task",
            aggregate_id=uuid7(),
            payload={"to": "READY"},
        )
        assert first.sequence == 1
        assert second.sequence == 2
        assert other_aggregate.sequence == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_dispatcher_marks_published_and_does_not_republish() -> None:
    """State-transition + negative test: draining an outbox row flips it to
    `published`; draining again does not re-publish it."""
    engine = new_engine()
    try:
        await truncate_outbox(engine)
        fixture = await seed_tenant(engine)
        service = EventService(engine)
        event = await service.append(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            event_type="MissionCommitted",
            aggregate_type="mission",
            aggregate_id=uuid7(),
            payload={},
        )
        dispatcher = OutboxDispatcher(engine)
        published: list[str] = []

        async def publish(item: Event) -> None:
            published.append(str(item.event_id))

        count = await dispatcher.drain(publish, limit=16)
        assert count == 1
        assert published == [str(event.event_id)]

        async with open_unit_of_work(
            engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            outbox_id_result = await uow.connection.execute(
                select(outbox.c.outbox_id).where(outbox.c.event_id == event.event_id)
            )
            row = await EventsRepository().get_outbox(
                uow.connection, outbox_id_result.scalar_one()
            )
            await uow.commit()
        assert row is not None
        assert row.status == "published"
        assert row.published_at is not None

        second_drain = await dispatcher.drain(publish, limit=16)
        assert second_drain == 0
        assert published == [str(event.event_id)]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_dispatcher_does_not_mark_published_when_publish_fails() -> None:
    """A crash/failure mid-publish leaves the row `pending` for the next
    drain — at-least-once, never zero-times (Chapter 16.3)."""
    engine = new_engine()
    try:
        await truncate_outbox(engine)
        fixture = await seed_tenant(engine)
        service = EventService(engine)
        await service.append(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            event_type="MissionCommitted",
            aggregate_type="mission",
            aggregate_id=uuid7(),
            payload={},
        )
        dispatcher = OutboxDispatcher(engine)

        async def failing_publish(item: Event) -> None:
            raise RuntimeError("simulated publish failure")

        with pytest.raises(RuntimeError):
            await dispatcher.drain(failing_publish, limit=16)

        published: list[str] = []

        async def publish(item: Event) -> None:
            published.append(str(item.event_id))

        count = await dispatcher.drain(publish, limit=16)
        assert count == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_command_ledger_returns_stored_record_on_repeat() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        ledger = CommandLedger(engine)

        first, first_is_new = await ledger.begin(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            idempotency_key="cmd-001",
            request_hash="abc",
        )
        second, second_is_new = await ledger.begin(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            idempotency_key="cmd-001",
            request_hash="abc",
        )
        assert first_is_new is True
        assert second_is_new is False
        assert second.command_id == first.command_id
        assert first.expires_at - first.created_at == COMMAND_IDEMPOTENCY_RETENTION_V1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_command_ledger_conflicts_on_hash_mismatch() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        ledger = CommandLedger(engine)
        await ledger.begin(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            idempotency_key="cmd-002",
            request_hash="abc",
        )
        with pytest.raises(DdeError) as captured:
            await ledger.begin(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                idempotency_key="cmd-002",
                request_hash="different",
            )
        assert captured.value.error_code == "VERSION_CONFLICT"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_command_ledger_rejects_expired_key() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        ledger = CommandLedger(engine)
        await ledger.begin(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            idempotency_key="cmd-003",
            request_hash=sha256_hex("payload"),
            ttl=timedelta(seconds=-1),
        )
        with pytest.raises(DdeError) as captured:
            await ledger.begin(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                idempotency_key="cmd-003",
                request_hash=sha256_hex("payload"),
            )
        assert captured.value.error_code == "VERSION_CONFLICT"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_command_ledger_complete_records_result() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        ledger = CommandLedger(engine)
        record, _ = await ledger.begin(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            idempotency_key="cmd-004",
            request_hash="abc",
        )
        completed = await ledger.complete(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            command_id=record.command_id,
            result={"outcome": "ok"},
        )
        assert completed.status == "completed"
        assert completed.result == {"outcome": "ok"}

        replay, is_new = await ledger.begin(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            idempotency_key="cmd-004",
            request_hash="abc",
        )
        assert is_new is False
        assert replay.status == "completed"
        assert replay.result == {"outcome": "ok"}
    finally:
        await engine.dispose()
