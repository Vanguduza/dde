"""Outbox dispatcher — drains `outbox` with `SELECT ... FOR UPDATE SKIP
LOCKED` and publishes at-least-once to Redis (Chapter 3.5, 16.3, 17.1).

**Divergence flagged for review (Chapter 16.3 already decides the primitive,
noted here for visibility):** publication target is a Redis **stream**
(`XADD`), not a list — Chapter 16.3 states this explicitly ("A dispatcher
publishes to Redis streams with at-least-once delivery"), so this is not a
free choice, just an explicit call-out of where it is implemented
(`RedisStreamPublisher` below).

**Locking design:** each pending row is claimed, published and marked
published inside its *own* short transaction (`limit=1` per iteration)
rather than one transaction per batch. `FOR UPDATE SKIP LOCKED` only holds a
row lock for the lifetime of the transaction that took it, so batching many
rows into one transaction would hold their locks for the whole batch's
publish latency and would roll every row in the batch back to `pending` if
any single publish failed. Locking one row per transaction keeps the
at-least-once contract precise: a row is marked `published` if and only if
`publish()` for that row returned without raising, and a crash between
publish and mark-published simply leaves the row `pending` for the next
drain to retry (duplicate delivery, tolerated per Chapter 16.3 because
consumers are idempotent on `event_id`).

The dispatcher intentionally does not scope its unit of work to one tenant:
it must drain outbox rows across every tenant, whereas
`engine.truth.db.open_unit_of_work` sets the `dde.tenant_id`/`dde.project_id`
GUCs that fail-closed RLS depends on. This is safe today because the local
dev role is a superuser and bypasses RLS entirely (see
`tests/support/db.py`); a production deployment must grant the dispatcher's
database role explicit cross-tenant access to `outbox` (e.g. a dedicated
system role, or an RLS policy carve-out for it) — that grant is
infrastructure configuration, not application code, and is out of scope for
S0.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.event import Event
from engine.core.clock import Clock, SystemClock
from engine.events.repository import EventsRepository
from engine.truth.db import PostgresUnitOfWork

Publisher = Callable[[Event], Awaitable[None]]

DEFAULT_STREAM_KEY = "dde:events"


@asynccontextmanager
async def open_dispatch_unit_of_work(
    engine: AsyncEngine,
) -> AsyncIterator[PostgresUnitOfWork]:
    """One transaction for the dispatcher, deliberately without the tenant
    GUCs `engine.truth.db.open_unit_of_work` sets — the dispatcher is a
    system-level process (Chapter 17.1), not a tenant-scoped request
    handler, and must see pending outbox rows for every tenant."""
    async with engine.connect() as connection:
        transaction = await connection.begin()
        uow = PostgresUnitOfWork(connection, transaction)
        try:
            yield uow
        except Exception:
            await uow.rollback()
            raise
        else:
            await uow.rollback()


class OutboxDispatcher:
    """Drains pending `outbox` rows and publishes each to Redis exactly
    once per successful `publish()` call, marking it published only after
    that call returns (at-least-once, Chapter 16.3). Safe to run as N
    concurrent instances (Chapter 3.5, 17.1): `SKIP LOCKED` guarantees two
    instances draining concurrently never both claim the same row."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: EventsRepository | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or EventsRepository()
        self._clock = clock or SystemClock()

    async def drain(self, publish: Publisher, *, limit: int = 16) -> int:
        """Publish up to `limit` pending rows, one row per transaction.
        Returns the number of rows this call published."""
        published = 0
        for _ in range(limit):
            async with open_dispatch_unit_of_work(self._engine) as uow:
                claimed = await self._repository.claim_pending_for_dispatch(
                    uow.connection, limit=1
                )
                if not claimed:
                    await uow.commit()
                    break
                row = claimed[0]
                event = Event.model_validate(row.payload)
                await publish(event)
                await self._repository.mark_published(
                    uow.connection, row.outbox_id, published_at=self._clock.now()
                )
                await uow.commit()
                published += 1
        return published


class SupportsXAdd(Protocol):
    """The one `redis.asyncio.Redis` method this module depends on, named
    as a `Protocol` so tests can supply a fake without importing the Redis
    client library."""

    async def xadd(self, name: str, fields: dict[str, str]) -> object: ...


class RedisStreamPublisher:
    """Publishes one event per `XADD` to a Redis stream (Chapter 16.3).
    A single, unsharded stream is the simplest correct primitive: per
    -aggregate ordering is carried by the event's own `sequence` field, not
    by stream partitioning, and Chapter 16.3 explicitly does not require
    global ordering across aggregates."""

    def __init__(
        self, client: SupportsXAdd, *, stream_key: str = DEFAULT_STREAM_KEY
    ) -> None:
        self._client = client
        self._stream_key = stream_key

    async def publish(self, event: Event) -> None:
        fields = {
            "event_id": str(event.event_id),
            "event_type": event.event_type,
            "aggregate_type": event.aggregate_type,
            "aggregate_id": str(event.aggregate_id),
            "sequence": str(event.sequence),
            "payload": event.model_dump_json(),
        }
        await self._client.xadd(self._stream_key, fields)
