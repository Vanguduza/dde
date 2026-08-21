"""Async repository for `context_packages` (Chapter 3.3, 3.8).

Every read and write here executes on the connection of an already-open
unit of work (Chapter 3.5); this module never begins or ends a
transaction itself.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.context.tables import (
    context_conflicts,
    context_critic_findings,
    context_packages,
)
from engine.contracts.context_conflict import ContextConflict
from engine.contracts.context_critic_finding import ContextCriticFinding
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


class ContextConflictRepository:
    """Reads and writes rows for `context_conflicts` -- the Chapter 5.6
    conflict-adjudication record, owned by `engine.context`."""

    async def insert_conflict(
        self, connection: AsyncConnection, record: ContextConflict
    ) -> None:
        dumped = record.model_dump()
        dumped["affected_success_criteria"] = list(dumped["affected_success_criteria"])
        await connection.execute(context_conflicts.insert().values(**dumped))

    async def list_for_package(
        self, connection: AsyncConnection, package_id: UUID
    ) -> list[ContextConflict]:
        result = await connection.execute(
            select(context_conflicts)
            .where(context_conflicts.c.package_id == package_id)
            .order_by(context_conflicts.c.created_at.asc())
        )
        return [
            ContextConflict.model_validate(dict(row)) for row in result.mappings().all()
        ]

    async def list_open_for_task(
        self, connection: AsyncConnection, task_id: UUID
    ) -> list[ContextConflict]:
        result = await connection.execute(
            select(context_conflicts)
            .where(
                context_conflicts.c.task_id == task_id,
                context_conflicts.c.status == "open",
            )
            .order_by(context_conflicts.c.created_at.asc())
        )
        return [
            ContextConflict.model_validate(dict(row)) for row in result.mappings().all()
        ]

    async def resolve(
        self,
        connection: AsyncConnection,
        conflict_id: UUID,
        *,
        resolution_method: str,
        resolved_at: object,
    ) -> int:
        result = await connection.execute(
            context_conflicts.update()
            .where(context_conflicts.c.conflict_id == conflict_id)
            .values(
                status="resolved",
                resolution_method=resolution_method,
                resolved_at=resolved_at,
                updated_at=resolved_at,
            )
        )
        return int(result.rowcount)


class ContextCriticFindingRepository:
    """Reads and writes rows for `context_critic_findings` -- the Chapter
    5.9 Context Critic record, owned by `engine.context`."""

    async def insert_finding(
        self, connection: AsyncConnection, record: ContextCriticFinding
    ) -> None:
        dumped = record.model_dump()
        dumped["trigger_reasons"] = list(dumped["trigger_reasons"])
        await connection.execute(context_critic_findings.insert().values(**dumped))

    async def list_for_package(
        self, connection: AsyncConnection, package_id: UUID
    ) -> list[ContextCriticFinding]:
        result = await connection.execute(
            select(context_critic_findings)
            .where(context_critic_findings.c.package_id == package_id)
            .order_by(context_critic_findings.c.created_at.asc())
        )
        return [
            ContextCriticFinding.model_validate(dict(row))
            for row in result.mappings().all()
        ]

    async def list_unreviewed_for_project(
        self, connection: AsyncConnection, tenant_id: UUID, project_id: UUID
    ) -> list[ContextCriticFinding]:
        result = await connection.execute(
            select(context_critic_findings)
            .where(
                context_critic_findings.c.tenant_id == tenant_id,
                context_critic_findings.c.project_id == project_id,
                context_critic_findings.c.requires_human_review.is_(True),
                context_critic_findings.c.reviewed.is_(False),
            )
            .order_by(context_critic_findings.c.created_at.asc())
        )
        return [
            ContextCriticFinding.model_validate(dict(row))
            for row in result.mappings().all()
        ]
