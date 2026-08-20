"""Production command idempotency ledger — the sole writer of
`command_idempotency` rows in PostgreSQL (Chapter 3.7, 12.5).

"Every externally visible mutation carries `command_id` and
`idempotency_key`. The command ledger records first-seen, in-progress,
completed and failed. A repeated command returns the stored result or
current status — it never launches a second mutation" (Chapter 12.5).

This service records a command as `in_progress` the moment it is first
seen (a single request handler receiving and starting to execute a command
are not distinguishable at this call boundary, so `first_seen` and
`in_progress` collapse into one atomic insert here) and moves it to
`completed`/`failed` once the underlying domain write finishes. A second
caller presenting the same `(tenant_id, idempotency_key)` never re-executes
the guarded body — it is handed back the first caller's stored status or
result instead (Chapter 12.5), and a caller supplying a different
`request_hash` for an existing key is refused outright rather than silently
proceeding against a different logical command.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from engine.contracts.command_idempotency import CommandIdempotency
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.tables import command_idempotency
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")

#: Chapter 3.7: "must exceed max retry window + max client reconnect window
#: + max mission pause duration. Default 30 days. Expiring a key earlier
#: permits a duplicate mutation, so this value is a policy-versioned
#: constant, not a tuning knob."
COMMAND_IDEMPOTENCY_RETENTION_V1 = timedelta(days=30)


class CommandLedgerRepository:
    """Reads and writes rows for the `command_idempotency` table."""

    async def insert_if_absent(
        self, connection: AsyncConnection, record: CommandIdempotency
    ) -> bool:
        """Atomically insert unless `(tenant_id, idempotency_key)` already
        exists. Uses `INSERT ... ON CONFLICT DO NOTHING` rather than a
        check-then-insert so two concurrent commands presenting the same key
        race safely at the database, not in application code."""
        statement = (
            pg_insert(command_idempotency)
            .values(**record.model_dump())
            .on_conflict_do_nothing(index_elements=["tenant_id", "idempotency_key"])
        )
        result = await connection.execute(statement)
        return result.rowcount == 1

    async def get_by_key(
        self, connection: AsyncConnection, tenant_id: UUID, idempotency_key: str
    ) -> CommandIdempotency | None:
        result = await connection.execute(
            select(command_idempotency).where(
                command_idempotency.c.tenant_id == tenant_id,
                command_idempotency.c.idempotency_key == idempotency_key,
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return CommandIdempotency.model_validate(dict(row))

    async def get_by_id(
        self, connection: AsyncConnection, command_id: UUID
    ) -> CommandIdempotency | None:
        result = await connection.execute(
            select(command_idempotency).where(
                command_idempotency.c.command_id == command_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return CommandIdempotency.model_validate(dict(row))

    async def update_status(
        self,
        connection: AsyncConnection,
        command_id: UUID,
        *,
        status: str,
        result: dict[str, object] | None,
        updated_at: datetime,
    ) -> None:
        await connection.execute(
            command_idempotency.update()
            .where(command_idempotency.c.command_id == command_id)
            .values(status=status, result=result, updated_at=updated_at)
        )


class CommandLedger:
    """Async, PostgreSQL-backed command idempotency ledger (Chapter 3.7,
    12.5). Each public method opens and commits its own unit of work unless
    one is supplied, so a caller composing a cross-module transaction
    (e.g. `engine.governance`) can share it instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: CommandLedgerRepository | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or CommandLedgerRepository()
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
            outcome = await body(owned)
            await owned.commit()
            return outcome

    async def begin(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        idempotency_key: str,
        request_hash: str,
        ttl: timedelta | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> tuple[CommandIdempotency, bool]:
        """Return `(record, is_new)`. `is_new` is `True` only for the
        caller that actually created the ledger row; every other caller
        presenting the same key gets `is_new=False` and must not proceed
        with the guarded mutation."""

        async def _op(active: PostgresUnitOfWork) -> tuple[CommandIdempotency, bool]:
            now = self._clock.now()
            candidate = CommandIdempotency(
                command_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                status="in_progress",
                result=None,
                expires_at=now + (ttl or COMMAND_IDEMPOTENCY_RETENTION_V1),
                created_at=now,
                updated_at=now,
            )
            inserted = await self._repository.insert_if_absent(
                active.connection, candidate
            )
            if inserted:
                return candidate, True
            existing = await self._repository.get_by_key(
                active.connection, tenant_id, idempotency_key
            )
            if existing is None:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Idempotency key insert conflicted but no row was found",
                    details={"idempotency_key": idempotency_key},
                )
            if existing.expires_at <= now:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Idempotency key expired; refusing a mutation that could duplicate",
                    details={"idempotency_key": idempotency_key},
                )
            if existing.request_hash != request_hash:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Idempotency key reused with a different request hash",
                    details={"idempotency_key": idempotency_key},
                )
            return existing, False

        return await self._run(uow, tenant_id, project_id, _op)

    async def complete(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        command_id: UUID,
        result: dict[str, object],
        uow: PostgresUnitOfWork | None = None,
    ) -> CommandIdempotency:
        async def _op(active: PostgresUnitOfWork) -> CommandIdempotency:
            await self._repository.update_status(
                active.connection,
                command_id,
                status="completed",
                result=result,
                updated_at=self._clock.now(),
            )
            updated = await self._repository.get_by_id(active.connection, command_id)
            if updated is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "Unknown command_id",
                    details={"command_id": str(command_id)},
                )
            return updated

        return await self._run(uow, tenant_id, project_id, _op)

    async def fail(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        command_id: UUID,
        result: dict[str, object] | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> None:
        async def _op(active: PostgresUnitOfWork) -> None:
            await self._repository.update_status(
                active.connection,
                command_id,
                status="failed",
                result=result,
                updated_at=self._clock.now(),
            )

        await self._run(uow, tenant_id, project_id, _op)
