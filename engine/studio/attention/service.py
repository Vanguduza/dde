"""Durable acknowledgements for derived Frontend Studio attention items."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.frontend_attention_acknowledgement import (
    FrontendAttentionAcknowledgement,
)
from engine.core.ids import uuid7
from engine.studio.tables import frontend_attention_acknowledgements
from engine.truth.db import open_unit_of_work


class AttentionAcknowledgementService:
    """Sole writer for project attention acknowledgements.

    The underlying finding/coverage/PXG source remains untouched. Acknowledgement
    only suppresses the same derived fingerprint until its source changes.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def acknowledged_keys(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> frozenset[str]:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                select(frontend_attention_acknowledgements.c.attention_key).where(
                    frontend_attention_acknowledgements.c.tenant_id == tenant_id,
                    frontend_attention_acknowledgements.c.project_id == project_id,
                )
            )
            return frozenset(str(row[0]) for row in result.all())

    async def acknowledge(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        attention_key: str,
        principal_id: UUID,
    ) -> FrontendAttentionAcknowledgement:
        if len(attention_key) != 64:
            from engine.core.errors import DdeError

            raise DdeError(
                "VALIDATION_FAILED",
                "attention_key must be a 64-character derived fingerprint",
            )
        now = datetime.now(UTC)
        record = FrontendAttentionAcknowledgement(
            acknowledgement_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            attention_key=attention_key,
            acknowledged_by=principal_id,
            acknowledged_at=now,
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            statement = (
                insert(frontend_attention_acknowledgements)
                .values(**record.model_dump())
                .on_conflict_do_update(
                    index_elements=[
                        frontend_attention_acknowledgements.c.project_id,
                        frontend_attention_acknowledgements.c.attention_key,
                    ],
                    set_={
                        "acknowledged_by": principal_id,
                        "acknowledged_at": now,
                        "updated_at": now,
                    },
                )
                .returning(frontend_attention_acknowledgements)
            )
            row = (await uow.connection.execute(statement)).mappings().one()
            await uow.commit()
        return FrontendAttentionAcknowledgement.model_validate(dict(row))
