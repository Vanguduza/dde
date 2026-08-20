"""Async repository for `external_effects` (Chapter 3.3, 3.8) -- owned
solely by `engine.recovery`."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.external_effect import ExternalEffect
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
