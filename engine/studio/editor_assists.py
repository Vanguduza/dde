"""Durable Frontend Studio editor-assist policy."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.frontend_editor_assist_state import FrontendEditorAssistState
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.studio.tables import frontend_editor_assist_states
from engine.truth.db import open_unit_of_work

ASSISTS = frozenset({"auto_layout", "ai_suggest"})


class EditorAssistService:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def get(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> FrontendEditorAssistState | None:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                select(frontend_editor_assist_states).where(
                    frontend_editor_assist_states.c.tenant_id == tenant_id,
                    frontend_editor_assist_states.c.project_id == project_id,
                )
            )
            row = result.mappings().first()
            return (
                None
                if row is None
                else FrontendEditorAssistState.model_validate(dict(row))
            )

    async def set(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        principal_id: UUID,
        assist: str,
        enabled: bool,
    ) -> FrontendEditorAssistState:
        if assist not in ASSISTS:
            raise DdeError(
                "VALIDATION_FAILED", "unknown editor assist", details={"assist": assist}
            )
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                select(frontend_editor_assist_states).where(
                    frontend_editor_assist_states.c.tenant_id == tenant_id,
                    frontend_editor_assist_states.c.project_id == project_id,
                )
            )
            row = result.mappings().first()
            if row is None:
                values = {"auto_layout": False, "ai_suggest": False}
                values[assist] = enabled
                record = FrontendEditorAssistState(
                    assist_state_id=uuid7(),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    auto_layout=values["auto_layout"],
                    ai_suggest=values["ai_suggest"],
                    updated_by=principal_id,
                    lock_version=1,
                    created_at=now,
                    updated_at=now,
                )
                await uow.connection.execute(
                    frontend_editor_assist_states.insert().values(**record.model_dump())
                )
            else:
                result = await uow.connection.execute(
                    update(frontend_editor_assist_states)
                    .where(
                        frontend_editor_assist_states.c.assist_state_id
                        == row["assist_state_id"]
                    )
                    .values(
                        **{
                            assist: enabled,
                            "updated_by": principal_id,
                            "updated_at": now,
                            "lock_version": frontend_editor_assist_states.c.lock_version
                            + 1,
                        }
                    )
                    .returning(frontend_editor_assist_states)
                )
                record = FrontendEditorAssistState.model_validate(
                    dict(result.mappings().one())
                )
            await uow.commit()
        return record
