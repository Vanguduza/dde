"""Async repository for `context_packages` (Chapter 3.3, 3.8).

Every read and write here executes on the connection of an already-open
unit of work (Chapter 3.5); this module never begins or ends a
transaction itself.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.context.tables import context_packages
from engine.contracts.context_package import ContextPackage


class ContextRepository:
    """Reads and writes rows for `context_packages` — the Chapter 3.8
    table owned by `engine.context`."""

    async def next_version(self, connection: AsyncConnection, task_id: UUID) -> int:
        result = await connection.execute(
            select(func.coalesce(func.max(context_packages.c.version), 0)).where(
                context_packages.c.task_id == task_id
            )
        )
        return int(result.scalar_one()) + 1

    async def insert_context_package(
        self, connection: AsyncConnection, record: ContextPackage
    ) -> None:
        await connection.execute(
            context_packages.insert().values(**record.model_dump())
        )

    async def get_context_package(
        self, connection: AsyncConnection, package_id: UUID
    ) -> ContextPackage | None:
        result = await connection.execute(
            select(context_packages).where(context_packages.c.package_id == package_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return ContextPackage.model_validate(dict(row))

    async def get_version(
        self, connection: AsyncConnection, task_id: UUID, version: int
    ) -> ContextPackage | None:
        result = await connection.execute(
            select(context_packages).where(
                context_packages.c.task_id == task_id,
                context_packages.c.version == version,
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return ContextPackage.model_validate(dict(row))

    async def list_versions_for_task(
        self, connection: AsyncConnection, task_id: UUID
    ) -> list[ContextPackage]:
        result = await connection.execute(
            select(context_packages)
            .where(context_packages.c.task_id == task_id)
            .order_by(context_packages.c.version.asc())
        )
        return [
            ContextPackage.model_validate(dict(row)) for row in result.mappings().all()
        ]

    async def list_for_project(
        self, connection: AsyncConnection, project_id: UUID, *, limit: int = 50
    ) -> list[ContextPackage]:
        result = await connection.execute(
            select(context_packages)
            .where(context_packages.c.project_id == project_id)
            .order_by(context_packages.c.created_at.desc())
            .limit(limit)
        )
        return [
            ContextPackage.model_validate(dict(row)) for row in result.mappings().all()
        ]

    async def list_for_mission(
        self, connection: AsyncConnection, mission_id: UUID
    ) -> list[ContextPackage]:
        result = await connection.execute(
            select(context_packages)
            .where(context_packages.c.mission_id == mission_id)
            .order_by(context_packages.c.created_at.asc())
        )
        return [
            ContextPackage.model_validate(dict(row)) for row in result.mappings().all()
        ]
