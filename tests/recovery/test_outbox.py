"""Outbox recovery: a crash before mark-published retries the same event."""

from __future__ import annotations

import pytest

from engine.contracts.event import Event
from engine.core.ids import uuid7
from tests.support.harness import build_harness


@pytest.mark.asyncio
async def test_unpublished_outbox_is_retried_without_duplicate_append() -> None:
    harness = build_harness()
    event = harness.events.append(
        event_type="MissionCommitted",
        aggregate_type="mission",
        aggregate_id=uuid7(),
        tenant_id=harness.tenant_id,
        project_id=harness.project_id,
        payload={"n": 1},
    )
    seen: list[str] = []

    async def publish(item: Event) -> None:
        seen.append(str(item.event_id))

    await harness.events.dispatch(publish)
    pending_again = harness.events.claim_pending()
    assert pending_again == []
    await harness.events.dispatch(publish)
    assert seen == [str(event.event_id)]


@pytest.mark.asyncio
async def test_crash_before_ack_replays_same_event_id() -> None:
    harness = build_harness()
    event = harness.events.append(
        event_type="MissionCommitted",
        aggregate_type="mission",
        aggregate_id=uuid7(),
        tenant_id=harness.tenant_id,
        project_id=harness.project_id,
        payload={"n": 1},
    )
    claimed = harness.events.claim_pending()
    assert claimed[0].event_id == event.event_id
    seen: list[str] = []

    async def publish(item: Event) -> None:
        seen.append(str(item.event_id))

    await publish(Event.model_validate(claimed[0].payload))
    await harness.events.dispatch(publish)
    assert seen == [str(event.event_id), str(event.event_id)]
