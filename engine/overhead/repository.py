"""Durable persistence for Chapter 16.4 overhead instrumentation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.control_plane_overhead_task import ControlPlaneOverheadTask
from engine.contracts.tenant_overhead_budget_settings import (
    TenantOverheadBudgetSettings,
)
from engine.overhead.tables import (
    control_plane_overhead_tasks,
    tenant_overhead_budget_settings,
)


class ControlPlaneOverheadRepository:
    async def insert_overhead_task(
        self, connection: AsyncConnection, record: ControlPlaneOverheadTask
    ) -> None:
        stmt = pg_insert(control_plane_overhead_tasks).values(**record.model_dump())
        stmt = stmt.on_conflict_do_nothing(index_elements=["overhead_task_id"])
        await connection.execute(stmt)

    async def get_tenant_budget_settings(
        self, connection: AsyncConnection, *, tenant_id: UUID
    ) -> TenantOverheadBudgetSettings | None:
        result = await connection.execute(
            select(tenant_overhead_budget_settings).where(
                tenant_overhead_budget_settings.c.tenant_id == tenant_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return TenantOverheadBudgetSettings.model_validate(dict(row))

    async def list_recent_overhead_tasks(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        project_id: UUID,
        effort: str,
        limit: int,
    ) -> list[ControlPlaneOverheadTask]:
        result = await connection.execute(
            select(control_plane_overhead_tasks)
            .where(
                control_plane_overhead_tasks.c.tenant_id == tenant_id,
                control_plane_overhead_tasks.c.project_id == project_id,
                control_plane_overhead_tasks.c.estimated_effort == effort,
            )
            .order_by(control_plane_overhead_tasks.c.created_at.desc())
            .limit(limit)
        )
        return [
            ControlPlaneOverheadTask.model_validate(dict(row))
            for row in result.mappings().all()
        ]

    async def list_recent_overhead_tasks_all_efforts(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        project_id: UUID,
        limit: int,
    ) -> list[ControlPlaneOverheadTask]:
        result = await connection.execute(
            select(control_plane_overhead_tasks)
            .where(
                control_plane_overhead_tasks.c.tenant_id == tenant_id,
                control_plane_overhead_tasks.c.project_id == project_id,
            )
            .order_by(control_plane_overhead_tasks.c.created_at.desc())
            .limit(limit)
        )
        return [
            ControlPlaneOverheadTask.model_validate(dict(row))
            for row in result.mappings().all()
        ]
