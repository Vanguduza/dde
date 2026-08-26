"""Async repository for Chapter 5.13 context-policy activation state.

Every read and write executes on an already-open unit of work (Chapter
3.5). This module never begins or ends a transaction itself.
`ContextService.compile()` may import this reader without a cycle;
`ContextActivationService` is the sole production writer.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.context.tables import context_activation_state
from engine.contracts.context_activation_state import ContextActivationState


def _state_values(record: ContextActivationState) -> dict[str, object]:
    return record.model_dump()


class ContextActivationRepository:
    """Reads and writes `context_activation_state`."""

    async def get(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        project_id: UUID,
    ) -> ContextActivationState | None:
        result = await connection.execute(
            select(context_activation_state).where(
                context_activation_state.c.tenant_id == tenant_id,
                context_activation_state.c.project_id == project_id,
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return ContextActivationState.model_validate(dict(row))

    async def upsert(
        self, connection: AsyncConnection, record: ContextActivationState
    ) -> ContextActivationState:
        values = _state_values(record)
        update_cols = {
            key: values[key]
            for key in (
                "context_mode",
                "candidate_arm",
                "last_certified_mode",
                "last_certified_arm",
                "last_promotion_run_id",
                "canary_fraction",
                "updated_at",
            )
        }
        await connection.execute(
            pg_insert(context_activation_state)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["tenant_id", "project_id"],
                set_=update_cols,
            )
        )
        loaded = await self.get(
            connection, tenant_id=record.tenant_id, project_id=record.project_id
        )
        if loaded is None:  # pragma: no cover - defensive
            raise RuntimeError("context activation upsert wrote no row")
        return loaded
