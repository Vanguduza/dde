"""Event store and outbox dispatcher recovery (Chapter 19.1): a fresh
engine/session against the same database sees rows a prior session
committed, an already-published row is never re-published by a fresh
dispatcher instance, and two dispatcher instances draining concurrently
never claim the same outbox row (Chapter 3.5's stated purpose for
`SELECT ... FOR UPDATE SKIP LOCKED`, Chapter 17.1's "SKIP LOCKED allows N
instances safely").
"""

from __future__ import annotations

import asyncio

import pytest

from engine.contracts.event import Event
from engine.core.ids import uuid7
from engine.events.dispatcher import OutboxDispatcher
from engine.events.repository import EventsRepository
from engine.events.service import EventService
from engine.truth.db import open_unit_of_work
from tests.support.db import new_engine, seed_tenant, truncate_outbox


@pytest.mark.asyncio
async def test_second_session_sees_committed_event_and_outbox_row() -> None:
    writer_engine = new_engine()
    fixture = await seed_tenant(writer_engine)
    aggregate_id = uuid7()
    written = await EventService(writer_engine).append(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        event_type="MissionCommitted",
        aggregate_type="mission",
        aggregate_id=aggregate_id,
        payload={"slug": "MISSION-ERP-000421"},
    )
    await writer_engine.dispose()  # simulate the writing process exiting

    reader_engine = new_engine()
    try:
        async with open_unit_of_work(
            reader_engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            reread = await EventsRepository().get_event(
                uow.connection, written.event_id
            )
            await uow.commit()
        assert reread is not None
        assert reread.event_id == written.event_id
        assert reread.payload == {"slug": "MISSION-ERP-000421"}
    finally:
        await reader_engine.dispose()


@pytest.mark.asyncio
async def test_fresh_dispatcher_does_not_republish_after_writer_exits() -> None:
    writer_engine = new_engine()
    await truncate_outbox(writer_engine)
    fixture = await seed_tenant(writer_engine)
    event = await EventService(writer_engine).append(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        event_type="MissionCommitted",
        aggregate_type="mission",
        aggregate_id=uuid7(),
        payload={},
    )
    first_published: list[str] = []

    async def publish_first(item: Event) -> None:
        first_published.append(str(item.event_id))

    await OutboxDispatcher(writer_engine).drain(publish_first, limit=16)
    await writer_engine.dispose()  # simulate the dispatcher process exiting

    assert first_published == [str(event.event_id)]

    fresh_dispatcher_engine = new_engine()
    try:
        second_published: list[str] = []

        async def publish_second(item: Event) -> None:
            second_published.append(str(item.event_id))

        count = await OutboxDispatcher(fresh_dispatcher_engine).drain(
            publish_second, limit=16
        )
        assert count == 0
        assert second_published == []
    finally:
        await fresh_dispatcher_engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_dispatcher_instances_never_claim_the_same_row() -> None:
    """Two dispatcher instances (distinct engines/connections, standing in
    for two processes) drain the same pending outbox concurrently. `SKIP
    LOCKED` must make their claims mutually exclusive: every pending row is
    delivered by exactly one of the two, never both, and none are lost."""
    seeding_engine = new_engine()
    await truncate_outbox(seeding_engine)
    fixture = await seed_tenant(seeding_engine)
    service = EventService(seeding_engine)
    seeded_ids = set()
    for _ in range(8):
        event = await service.append(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            event_type="MissionCommitted",
            aggregate_type="mission",
            aggregate_id=uuid7(),
            payload={},
        )
        seeded_ids.add(str(event.event_id))
    await seeding_engine.dispose()

    engine_a = new_engine()
    engine_b = new_engine()
    try:
        delivered_a: list[str] = []
        delivered_b: list[str] = []

        async def publish_a(item: Event) -> None:
            delivered_a.append(str(item.event_id))

        async def publish_b(item: Event) -> None:
            delivered_b.append(str(item.event_id))

        counts = await asyncio.gather(
            OutboxDispatcher(engine_a).drain(publish_a, limit=8),
            OutboxDispatcher(engine_b).drain(publish_b, limit=8),
        )

        assert sum(counts) == len(seeded_ids)
        assert set(delivered_a) & set(delivered_b) == set()
        assert set(delivered_a) | set(delivered_b) == seeded_ids
    finally:
        await engine_a.dispose()
        await engine_b.dispose()
