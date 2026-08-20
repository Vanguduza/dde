"""Production audit ledger — the sole writer of `audit_events` in PostgreSQL
(Chapter 3.7, 3.8).

Unlike the in-memory `AuditLedger` test double in `engine.audit.ledger`, this
service persists the hash chain durably so a decision's audit trail survives
a process restart, matching `engine.truth.service.TruthService`'s production
pattern (Chapter 3.5: a transaction may span module boundaries, so a caller
composing a cross-module transaction — e.g. `engine.governance` recording a
decision alongside its audit entry — can pass an already-open unit of work).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.audit.ledger import audit_entry_hash
from engine.audit.repository import AuditRepository
from engine.contracts.audit_event import AuditEvent
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")


class AuditService:
    """Async, PostgreSQL-backed writer for the hash-chained `audit_events`
    ledger. Each public method opens and commits its own unit of work unless
    one is supplied, so a caller composing a cross-module transaction can
    share it instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: AuditRepository | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or AuditRepository()
        self._clock = clock or SystemClock()

    async def _run(
        self,
        uow: PostgresUnitOfWork | None,
        tenant_id: UUID,
        project_id: UUID | None,
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
        event_type: str,
        payload: dict[str, object],
        project_id: UUID | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> AuditEvent:
        async def _op(active: PostgresUnitOfWork) -> AuditEvent:
            prev = await self._repository.get_latest(active.connection, tenant_id)
            now = self._clock.now()
            audit_event_id = uuid7()
            prev_hash = None if prev is None else prev.entry_hash
            record = AuditEvent(
                audit_event_id=audit_event_id,
                tenant_id=tenant_id,
                project_id=project_id,
                event_type=event_type,
                sequence=1 if prev is None else prev.sequence + 1,
                prev_hash=prev_hash,
                entry_hash=audit_entry_hash(
                    prev_hash=prev_hash,
                    audit_event_id=audit_event_id,
                    event_type=event_type,
                    payload=payload,
                ),
                payload=payload,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert(active.connection, record)
            return record

        return await self._run(uow, tenant_id, project_id, _op)

    async def verify_chain(
        self,
        *,
        tenant_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> None:
        async def _op(active: PostgresUnitOfWork) -> None:
            prev_hash: str | None = None
            for entry in await self._repository.list_for_tenant(
                active.connection, tenant_id
            ):
                expected = audit_entry_hash(
                    prev_hash=prev_hash,
                    audit_event_id=entry.audit_event_id,
                    event_type=entry.event_type,
                    payload=entry.payload,
                )
                if entry.prev_hash != prev_hash or entry.entry_hash != expected:
                    raise DdeError(
                        "POLICY_DENIED",
                        "Audit ledger hash chain is broken",
                        details={"audit_event_id": str(entry.audit_event_id)},
                    )
                prev_hash = entry.entry_hash

        return await self._run(uow, tenant_id, None, _op)
