"""Async repository for `external_effects` (Chapter 3.3, 3.8) -- owned
solely by `engine.recovery`."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.external_effect import ExternalEffect
from engine.recovery.scope import BLOCKING_STATUSES
from engine.recovery.tables import external_effects


class ExternalEffectRepository:
    """Reads and writes rows for `external_effects`."""

    async def insert_effect(
        self, connection: AsyncConnection, record: ExternalEffect
    ) -> None:
        await connection.execute(
            external_effects.insert().values(**record.model_dump())
        )

    async def update_fields(
        self,
        connection: AsyncConnection,
        effect_id: UUID,
        *,
        fields: dict[str, object],
    ) -> int:
        result = await connection.execute(
            external_effects.update()
            .where(external_effects.c.effect_id == effect_id)
            .values(**fields)
        )
        return result.rowcount

    async def get_by_id(
        self, connection: AsyncConnection, effect_id: UUID
    ) -> ExternalEffect | None:
        result = await connection.execute(
            select(external_effects).where(external_effects.c.effect_id == effect_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return ExternalEffect.model_validate(dict(row))

    async def list_for_run(
        self, connection: AsyncConnection, worker_run_id: UUID
    ) -> list[ExternalEffect]:
        result = await connection.execute(
            select(external_effects)
            .where(external_effects.c.worker_run_id == worker_run_id)
            .order_by(external_effects.c.created_at.asc())
        )
        return [
            ExternalEffect.model_validate(dict(row)) for row in result.mappings().all()
        ]

    async def list_blocking_for_scope(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        target_system: str,
        target_resource: str,
        operation: str,
    ) -> list[ExternalEffect]:
        """Live rows that refuse a new mutation of this logical scope
        (Chapter 12.4). See `engine.recovery.scope`."""
        result = await connection.execute(
            select(external_effects)
            .where(
                external_effects.c.tenant_id == tenant_id,
                external_effects.c.project_id == project_id,
                external_effects.c.mission_id == mission_id,
                external_effects.c.target_system == target_system,
                external_effects.c.target_resource == target_resource,
                external_effects.c.operation == operation,
                or_(
                    external_effects.c.status.in_(BLOCKING_STATUSES),
                    and_(
                        external_effects.c.status == "RECONCILED",
                        external_effects.c.confirmed_at.is_not(None),
                    ),
                ),
            )
            .order_by(external_effects.c.created_at.asc())
        )
        return [
            ExternalEffect.model_validate(dict(row)) for row in result.mappings().all()
        ]

    async def list_unreconciled_for_mission(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
    ) -> list[ExternalEffect]:
        result = await connection.execute(
            select(external_effects)
            .where(
                external_effects.c.tenant_id == tenant_id,
                external_effects.c.project_id == project_id,
                external_effects.c.mission_id == mission_id,
                external_effects.c.status.in_(BLOCKING_STATUSES),
            )
            .order_by(external_effects.c.created_at.asc())
        )
        return [
            ExternalEffect.model_validate(dict(row)) for row in result.mappings().all()
        ]
