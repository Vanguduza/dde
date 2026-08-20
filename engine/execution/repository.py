"""Async repository for `execution_plans` (Chapter 3.3, 3.8).

Every read and write here executes on the connection of an already-open
unit of work (Chapter 3.5); this module never begins or ends a transaction
itself.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.execution_plan import ExecutionPlan
from engine.execution.tables import execution_plans


class ExecutionPlanRepository:
    """Reads and writes rows for `execution_plans` — the Chapter 3.8 table
    owned by `engine.execution`."""

    async def insert_plan(
        self, connection: AsyncConnection, record: ExecutionPlan
    ) -> None:
        await connection.execute(execution_plans.insert().values(**record.model_dump()))

    async def get_plan(
        self, connection: AsyncConnection, plan_id: UUID
    ) -> ExecutionPlan | None:
        result = await connection.execute(
            select(execution_plans).where(execution_plans.c.plan_id == plan_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return ExecutionPlan.model_validate(dict(row))

    async def list_for_task(
        self, connection: AsyncConnection, task_id: UUID
    ) -> list[ExecutionPlan]:
        result = await connection.execute(
            select(execution_plans)
            .where(execution_plans.c.task_id == task_id)
            .order_by(execution_plans.c.created_at.asc())
        )
        return [
            ExecutionPlan.model_validate(dict(row)) for row in result.mappings().all()
        ]

    async def update_status(
        self,
        connection: AsyncConnection,
        plan_id: UUID,
        *,
        status: str,
        approved_at: object = None,
        started_at: object = None,
        ended_at: object = None,
    ) -> int:
        """`ExecutionPlan`'s definition is immutable (Chapter 3.10); only
        `status` and its timestamp companions ever change (Chapter 3.8:
        "Definition immutable; status mutable"). No `lock_version` column
        exists on this table (unlike `ExecutionEnvironment`/`Workspace`) —
        Chapter 7.1's field list omits one, consistent with `RouteDecision`
        having none either."""
        values: dict[str, object] = {"status": status}
        if approved_at is not None:
            values["approved_at"] = approved_at
        if started_at is not None:
            values["started_at"] = started_at
        if ended_at is not None:
            values["ended_at"] = ended_at
        result = await connection.execute(
            execution_plans.update()
            .where(execution_plans.c.plan_id == plan_id)
            .values(**values)
        )
        return int(result.rowcount)
