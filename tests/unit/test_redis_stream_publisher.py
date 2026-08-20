"""`RedisStreamPublisher` against a real local Redis (Chapter 16.3: "A
dispatcher publishes to Redis streams with at-least-once delivery").
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import redis.asyncio as redis

from engine.contracts.event import Event
from engine.core.ids import uuid7
from engine.events.dispatcher import RedisStreamPublisher
from engine.gateway.settings import get_settings


def _sample_event() -> Event:
    now = datetime.now(UTC)
    return Event(
        event_id=uuid7(),
        event_type="MissionCommitted",
        aggregate_type="mission",
        aggregate_id=uuid7(),
        tenant_id=uuid7(),
        project_id=uuid7(),
        sequence=1,
        occurred_at=now,
        correlation_id=str(uuid7()),
        payload={"slug": "MISSION-ERP-000421"},
        schema_version="1",
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_publish_xadds_event_fields_to_the_stream() -> None:
    client = redis.from_url(get_settings().redis_url)
    stream_key = f"dde:events:test:{uuid.uuid4().hex}"
    try:
        publisher = RedisStreamPublisher(client, stream_key=stream_key)
        event = _sample_event()

        await publisher.publish(event)

        entries = await client.xrange(stream_key)
        assert len(entries) == 1
        _entry_id, fields = entries[0]
        assert fields[b"event_id"].decode() == str(event.event_id)
        assert fields[b"event_type"].decode() == "MissionCommitted"
        assert fields[b"sequence"].decode() == "1"
    finally:
        await client.delete(stream_key)
        await client.aclose()
