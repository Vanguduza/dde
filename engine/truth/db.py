"""PostgreSQL unit of work for Project Truth writes (Chapter 3.2, 3.5).

One transaction per unit of work, scoped to a tenant/project via `SELECT
set_config(..., true)` (the `SET LOCAL` equivalent that supports bind
parameters). The GUCs reset at transaction end; a caller that never sets them
gets a connection where `current_setting('dde.tenant_id', true)` is NULL, so
the fail-closed RLS predicate in `schemas/sql/0001_stage1.sql` matches no rows.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncTransaction,
    create_async_engine,
)


def build_engine(database_url: str) -> AsyncEngine:
    """One engine per process; each unit of work checks out its own connection."""
    return create_async_engine(database_url, pool_pre_ping=True)


class PostgresUnitOfWork:
    """One open PostgreSQL transaction (Chapter 3.5). Modules sharing a unit of
    work must not open an independent transaction of their own."""

    def __init__(
        self, connection: AsyncConnection, transaction: AsyncTransaction
    ) -> None:
        self.connection = connection
        self._transaction = transaction
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        if self.committed or self.rolled_back:
            return
        await self._transaction.commit()
        self.committed = True

    async def rollback(self) -> None:
        if self.committed or self.rolled_back:
            return
        await self._transaction.rollback()
        self.rolled_back = True


async def _set_tenant_scope(
    connection: AsyncConnection, *, tenant_id: UUID, project_id: UUID | None
) -> None:
    await connection.execute(
        text("SELECT set_config('dde.tenant_id', :value, true)"),
        {"value": str(tenant_id)},
    )
    if project_id is not None:
        await connection.execute(
            text("SELECT set_config('dde.project_id', :value, true)"),
            {"value": str(project_id)},
        )


@asynccontextmanager
async def open_unit_of_work(
    engine: AsyncEngine,
    *,
    tenant_id: UUID,
    project_id: UUID | None = None,
) -> AsyncIterator[PostgresUnitOfWork]:
    """Open one transaction and set the tenant/project GUCs RLS depends on.

    The caller must call `commit()` explicitly; an unhandled exception or a
    context exit without a prior commit rolls the transaction back.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()
        uow = PostgresUnitOfWork(connection, transaction)
        try:
            await _set_tenant_scope(
                connection, tenant_id=tenant_id, project_id=project_id
            )
            yield uow
        except Exception:
            await uow.rollback()
            raise
        else:
            await uow.rollback()
