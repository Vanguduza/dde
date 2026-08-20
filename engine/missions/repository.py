"""Async repository for Mission Kernel tables (Chapter 3.3, 3.8).

Every read and write here executes on the connection of an already-open unit
of work (Chapter 3.5); this module never begins or ends a transaction
itself.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.mission import Mission
from engine.contracts.task import Task
from engine.missions.tables import missions, tasks


class MissionsRepository:
    """Reads and writes rows for `missions` and `tasks` — the Chapter 3.8
    mission-spine tables owned by `engine.missions`. `task_graphs` and
    `task_graph_edges` are owned by `engine.planning.repository`
    instead."""

    async def insert_mission(
        self, connection: AsyncConnection, record: Mission
    ) -> None:
        await connection.execute(missions.insert().values(**record.model_dump()))

    async def get_mission(
        self, connection: AsyncConnection, mission_id: UUID
    ) -> Mission | None:
        result = await connection.execute(
            select(missions).where(missions.c.mission_id == mission_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return Mission.model_validate(dict(row))

    async def list_missions(
        self, connection: AsyncConnection, *, project_id: UUID
    ) -> list[Mission]:
        result = await connection.execute(
            select(missions)
            .where(missions.c.project_id == project_id)
            .order_by(missions.c.created_at.desc())
        )
        return [Mission.model_validate(dict(row)) for row in result.mappings().all()]

    async def list_tasks_for_mission(
        self, connection: AsyncConnection, mission_id: UUID
    ) -> list[Task]:
        result = await connection.execute(
            select(tasks)
            .where(tasks.c.mission_id == mission_id)
            .order_by(tasks.c.created_at.asc())
        )
        return [Task.model_validate(dict(row)) for row in result.mappings().all()]

    async def get_mission_by_slug(
        self, connection: AsyncConnection, project_id: UUID, slug: str
    ) -> Mission | None:
        result = await connection.execute(
            select(missions).where(
                missions.c.project_id == project_id, missions.c.slug == slug
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return Mission.model_validate(dict(row))

    async def update_mission_status(
        self,
        connection: AsyncConnection,
        mission_id: UUID,
        *,
        status: str,
        expected_lock_version: int,
        updated_at: datetime,
    ) -> int:
        """Optimistic-lock update (Chapter 3.5): the `WHERE lock_version =
        expected` clause is what makes a stale concurrent write affect zero
        rows instead of silently overwriting a newer one."""
        result = await connection.execute(
            missions.update()
            .where(
                missions.c.mission_id == mission_id,
                missions.c.lock_version == expected_lock_version,
            )
            .values(
                status=status,
                lock_version=missions.c.lock_version + 1,
                updated_at=updated_at,
            )
        )
        return int(result.rowcount)

    async def insert_task(self, connection: AsyncConnection, record: Task) -> None:
        await connection.execute(tasks.insert().values(**record.model_dump()))

    async def list_tasks_for_graph(
        self, connection: AsyncConnection, graph_id: UUID
    ) -> list[Task]:
        result = await connection.execute(
            select(tasks)
            .where(tasks.c.graph_id == graph_id)
            .order_by(tasks.c.created_at.asc())
        )
        return [Task.model_validate(dict(row)) for row in result.mappings().all()]
