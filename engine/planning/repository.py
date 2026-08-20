"""Async repository for TaskGraph tables (Chapter 3.8).

Every read and write here executes on the connection of an already-open unit
of work (Chapter 3.5); this module never begins or ends a transaction
itself.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.task_graph import TaskGraph
from engine.contracts.task_graph_edge import TaskGraphEdge
from engine.planning.tables import task_graph_edges, task_graphs


class TaskGraphRepository:
    """Reads and writes rows for `task_graphs` and `task_graph_edges` — the
    Chapter 3.8 TaskGraph-spine tables owned by `engine.planning`."""

    async def insert_task_graph(
        self, connection: AsyncConnection, record: TaskGraph
    ) -> None:
        await connection.execute(task_graphs.insert().values(**record.model_dump()))

    async def get_task_graph(
        self, connection: AsyncConnection, graph_id: UUID
    ) -> TaskGraph | None:
        result = await connection.execute(
            select(task_graphs).where(task_graphs.c.graph_id == graph_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return TaskGraph.model_validate(dict(row))

    async def update_task_graph_status(
        self,
        connection: AsyncConnection,
        graph_id: UUID,
        *,
        status: str,
        expected_lock_version: int,
        updated_at: datetime,
    ) -> int:
        """Optimistic-lock update (Chapter 3.5): the `WHERE lock_version =
        expected` clause is what makes a stale concurrent write affect zero
        rows instead of silently overwriting a newer one."""
        result = await connection.execute(
            task_graphs.update()
            .where(
                task_graphs.c.graph_id == graph_id,
                task_graphs.c.lock_version == expected_lock_version,
            )
            .values(
                status=status,
                lock_version=task_graphs.c.lock_version + 1,
                updated_at=updated_at,
            )
        )
        return int(result.rowcount)

    async def insert_edge(
        self, connection: AsyncConnection, record: TaskGraphEdge
    ) -> None:
        await connection.execute(
            task_graph_edges.insert().values(**record.model_dump())
        )

    async def list_edges_for_graph(
        self, connection: AsyncConnection, graph_id: UUID
    ) -> list[TaskGraphEdge]:
        result = await connection.execute(
            select(task_graph_edges)
            .where(task_graph_edges.c.graph_id == graph_id)
            .order_by(task_graph_edges.c.created_at.asc())
        )
        return [
            TaskGraphEdge.model_validate(dict(row)) for row in result.mappings().all()
        ]
