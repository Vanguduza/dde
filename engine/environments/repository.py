"""Async repository for `execution_environments` (Chapter 3.3, 3.8).

Every read and write here executes on the connection of an already-open
unit of work (Chapter 3.5); this module never begins or ends a transaction
itself.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.execution_environment import ExecutionEnvironment
from engine.environments.tables import execution_environments


class ExecutionEnvironmentRepository:
    """Reads and writes rows for `execution_environments` — the Chapter 3.8
    table owned by `engine.environments`."""

    async def insert_environment(
        self, connection: AsyncConnection, record: ExecutionEnvironment
    ) -> None:
        await connection.execute(
            execution_environments.insert().values(**record.model_dump(by_alias=True))
        )

    async def get_environment(
        self, connection: AsyncConnection, environment_id: UUID
    ) -> ExecutionEnvironment | None:
        result = await connection.execute(
            select(execution_environments).where(
                execution_environments.c.environment_id == environment_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return ExecutionEnvironment.model_validate(dict(row))

    async def update_environment(
        self,
        connection: AsyncConnection,
        environment_id: UUID,
        *,
        expected_lock_version: int,
        updated_at: datetime,
        fields: dict[str, Any],
    ) -> int:
        """Optimistic-lock update (Chapter 3.5): the `WHERE lock_version =
        expected` clause is what makes a stale concurrent write affect zero
        rows instead of silently overwriting a newer one."""
        result = await connection.execute(
            execution_environments.update()
            .where(
                execution_environments.c.environment_id == environment_id,
                execution_environments.c.lock_version == expected_lock_version,
            )
            .values(
                **fields,
                lock_version=execution_environments.c.lock_version + 1,
                updated_at=updated_at,
            )
        )
        return int(result.rowcount)
