"""Event store, transactional outbox and command ledger.

`EventService`, `OutboxDispatcher` and `CommandLedger` (all backed by
PostgreSQL/Redis) are the production writers. `EventEngine` and `EventStore`
are an in-memory test double only, still used by `engine.missions.kernel` —
they never touch a database and must not be used as a production store.
"""

from engine.events.dispatcher import (
    OutboxDispatcher,
    RedisStreamPublisher,
    open_dispatch_unit_of_work,
)
from engine.events.engine import EventEngine, EventStore
from engine.events.idempotency import (
    COMMAND_IDEMPOTENCY_RETENTION_V1,
    CommandLedger,
    CommandLedgerRepository,
)
from engine.events.repository import EventsRepository
from engine.events.service import EventService

__all__ = [
    "COMMAND_IDEMPOTENCY_RETENTION_V1",
    "CommandLedger",
    "CommandLedgerRepository",
    "EventEngine",
    "EventService",
    "EventStore",
    "EventsRepository",
    "OutboxDispatcher",
    "RedisStreamPublisher",
    "open_dispatch_unit_of_work",
]
