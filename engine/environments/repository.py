"""Async repository for `execution_environments` (Chapter 3.3, 3.8).

Every read and write here executes on the connection of an already-open
unit of work (Chapter 3.5); this module never begins or ends a transaction
itself.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
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

    async def list_pooled_for_digest(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        project_id: UUID,
        environment_class: str,
        image_digest: str,
        limit: int | None = None,
    ) -> list[ExecutionEnvironment]:
        """Claim one READY (pooled) environment matching the current
        `(class, image_digest)` tuple for this tenant and project.

        `FOR UPDATE SKIP LOCKED` (Chapter 3.5) makes concurrent acquisition
        safe: a row another planner has already locked is skipped rather than
        awaited, and the explicit tenant/project predicates are the Chapter
        7.4 cross-tenant-reuse guard (defence in depth on top of RLS — the
        local dev `dde` role is a superuser and bypasses RLS, so these
        predicates are load-bearing, not redundant)."""
        stmt = (
            select(execution_environments)
            .where(
                execution_environments.c.tenant_id == tenant_id,
                execution_environments.c.project_id == project_id,
                execution_environments.c["class"] == environment_class,
                execution_environments.c.image_digest == image_digest,
                execution_environments.c.lifecycle_state == "READY",
            )
            .order_by(execution_environments.c.created_at.asc())
            .with_for_update(skip_locked=True)
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await connection.execute(stmt)
        return [
            ExecutionEnvironment.model_validate(dict(row))
            for row in result.mappings().all()
        ]

    async def count_pooled_for_digest(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        project_id: UUID,
        environment_class: str,
        image_digest: str,
    ) -> int:
        """Number of READY (pooled) environments at the current digest, used
        by `top_up` to decide how many more to provision toward Chapter 7.4's
        default N=2."""
        result = await connection.execute(
            select(func.count())
            .select_from(execution_environments)
            .where(
                execution_environments.c.tenant_id == tenant_id,
                execution_environments.c.project_id == project_id,
                execution_environments.c["class"] == environment_class,
                execution_environments.c.image_digest == image_digest,
                execution_environments.c.lifecycle_state == "READY",
            )
        )
        return int(result.scalar_one())

    async def list_pooled_for_class(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        project_id: UUID,
        environment_class: str,
    ) -> list[ExecutionEnvironment]:
        """Every READY (pooled) environment for this tenant/project/class,
        regardless of digest — used by `top_up` to retire stale-digest pooled
        environments when the toolchain image changes (Chapter 7.4 image
        discipline)."""
        result = await connection.execute(
            select(execution_environments)
            .where(
                execution_environments.c.tenant_id == tenant_id,
                execution_environments.c.project_id == project_id,
                execution_environments.c["class"] == environment_class,
                execution_environments.c.lifecycle_state == "READY",
            )
            .order_by(execution_environments.c.created_at.asc())
        )
        return [
            ExecutionEnvironment.model_validate(dict(row))
            for row in result.mappings().all()
        ]
