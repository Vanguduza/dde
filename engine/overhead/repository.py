"""Durable persistence for Chapter 16.4 overhead instrumentation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Float, cast, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.control_plane_overhead_task import ControlPlaneOverheadTask
from engine.contracts.tenant_overhead_budget_settings import (
    TenantOverheadBudgetSettings,
)
from engine.contracts.workload_class_cost_metrics import WorkloadClassCostMetrics
from engine.core.ids import uuid7
from engine.overhead.tables import (
    control_plane_overhead_tasks,
    tenant_overhead_budget_settings,
    workload_class_cost_metrics,
)


class ControlPlaneOverheadRepository:
    async def insert_overhead_task(
        self, connection: AsyncConnection, record: ControlPlaneOverheadTask
    ) -> None:
        stmt = pg_insert(control_plane_overhead_tasks).values(**record.model_dump())
        stmt = stmt.on_conflict_do_nothing(index_elements=["overhead_task_id"])
        await connection.execute(stmt)

    async def get_by_worker_run_id(
        self, connection: AsyncConnection, worker_run_id: UUID
    ) -> ControlPlaneOverheadTask | None:
        result = await connection.execute(
            select(control_plane_overhead_tasks).where(
                control_plane_overhead_tasks.c.worker_run_id == worker_run_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return ControlPlaneOverheadTask.model_validate(dict(row))

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

    async def record_verified_success(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        project_id: UUID,
        workload_class: str,
        overhead_tokens: int,
        now: datetime,
    ) -> None:
        stmt = pg_insert(workload_class_cost_metrics).values(
            metric_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            workload_class=workload_class,
            verified_success_count=1,
            total_overhead_tokens=overhead_tokens,
            cost_tokens_per_verified_success=float(overhead_tokens),
            created_at=now,
            updated_at=now,
        )
        total = workload_class_cost_metrics.c.total_overhead_tokens + overhead_tokens
        count = workload_class_cost_metrics.c.verified_success_count + 1
        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "project_id", "workload_class"],
            set_={
                "verified_success_count": count,
                "total_overhead_tokens": total,
                "cost_tokens_per_verified_success": cast(total, Float)
                / cast(count, Float),
                "updated_at": now,
            },
        )
        await connection.execute(stmt)

    async def list_cost_metrics_for_project(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        project_id: UUID,
    ) -> list[WorkloadClassCostMetrics]:
        result = await connection.execute(
            select(workload_class_cost_metrics)
            .where(
                workload_class_cost_metrics.c.tenant_id == tenant_id,
                workload_class_cost_metrics.c.project_id == project_id,
            )
            .order_by(workload_class_cost_metrics.c.workload_class.asc())
        )
        return [
            WorkloadClassCostMetrics.model_validate(dict(row))
            for row in result.mappings().all()
        ]
