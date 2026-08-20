"""Event store, outbox and command ledger."""

from __future__ import annotations

import pytest

from engine.core.errors import DdeError
from engine.core.ids import uuid7
from tests.support.harness import build_harness


def test_append_writes_event_and_pending_outbox() -> None:
    harness = build_harness()
    event = harness.events.append(
        event_type="MissionCommitted",
        aggregate_type="mission",
        aggregate_id=uuid7(),
        tenant_id=harness.tenant_id,
        project_id=harness.project_id,
        payload={"status": "CREATED"},
    )
    assert event.sequence == 1
    pending = harness.event_store.unpublished()
    assert len(pending) == 1
    assert pending[0].event_id == event.event_id
    assert pending[0].status == "pending"


@pytest.mark.asyncio
async def test_outbox_dispatch_marks_published() -> None:
    harness = build_harness()
    harness.events.append(
        event_type="MissionCommitted",
        aggregate_type="mission",
        aggregate_id=uuid7(),
        tenant_id=harness.tenant_id,
        project_id=harness.project_id,
        payload={},
    )
    published: list[str] = []

    async def publish(event) -> None:
        published.append(event.event_type)

    count = await harness.events.dispatch(publish)
    assert count == 1
    assert published == ["MissionCommitted"]
    assert harness.event_store.unpublished() == []


def test_duplicate_idempotency_key_returns_stored_command() -> None:
    harness = build_harness()
    first, created = harness.events.accept_command(
        tenant_id=harness.tenant_id,
        project_id=harness.project_id,
        idempotency_key="mission.create:1",
        request_hash="abc",
    )
    second, created_again = harness.events.accept_command(
        tenant_id=harness.tenant_id,
        project_id=harness.project_id,
        idempotency_key="mission.create:1",
        request_hash="abc",
    )
    assert created is True
    assert created_again is False
    assert first.command_id == second.command_id


def test_idempotency_key_conflict_on_hash_mismatch() -> None:
    harness = build_harness()
    harness.events.accept_command(
        tenant_id=harness.tenant_id,
        project_id=harness.project_id,
        idempotency_key="mission.create:1",
        request_hash="abc",
    )
    with pytest.raises(DdeError) as captured:
        harness.events.accept_command(
            tenant_id=harness.tenant_id,
            project_id=harness.project_id,
            idempotency_key="mission.create:1",
            request_hash="different",
        )
    assert captured.value.error_code == "VERSION_CONFLICT"
