"""Preview scenario simulation, separate from browser runtime attestation."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.frontend_preview_scenario import FrontendPreviewScenario
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.studio.tables import frontend_preview_scenarios, frontend_preview_sessions
from engine.truth.db import open_unit_of_work

SCENARIOS = frozenset({"DEFAULT", "LOADING", "EMPTY", "ERROR", "OFFLINE", "ROLE"})


class PreviewScenarioService:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def get(
        self, *, tenant_id: UUID, project_id: UUID, preview_session_id: UUID
    ) -> FrontendPreviewScenario | None:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                select(frontend_preview_scenarios).where(
                    frontend_preview_scenarios.c.preview_session_id
                    == preview_session_id,
                    frontend_preview_scenarios.c.tenant_id == tenant_id,
                    frontend_preview_scenarios.c.project_id == project_id,
                )
            )
            row = result.mappings().first()
            return (
                None
                if row is None
                else FrontendPreviewScenario.model_validate(dict(row))
            )

    async def set(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        preview_session_id: UUID,
        principal_id: UUID,
        scenario: str,
        role: str | None = None,
    ) -> FrontendPreviewScenario:
        if scenario not in SCENARIOS:
            raise DdeError(
                "SCENARIO_UNSUPPORTED",
                "unsupported preview scenario",
                details={"scenario": scenario, "known": sorted(SCENARIOS)},
            )
        if scenario == "ROLE" and not role:
            raise DdeError("VALIDATION_FAILED", "ROLE scenario requires a role")
        if scenario != "ROLE":
            role = None
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            preview = await uow.connection.execute(
                select(frontend_preview_sessions.c.preview_session_id).where(
                    frontend_preview_sessions.c.preview_session_id
                    == preview_session_id,
                    frontend_preview_sessions.c.tenant_id == tenant_id,
                    frontend_preview_sessions.c.project_id == project_id,
                )
            )
            if preview.first() is None:
                raise DdeError(
                    "CONTEXT_INCOMPLETE", "preview session is not in this project"
                )
            existing = await uow.connection.execute(
                select(frontend_preview_scenarios).where(
                    frontend_preview_scenarios.c.preview_session_id
                    == preview_session_id
                )
            )
            row = existing.mappings().first()
            if row is None:
                record = FrontendPreviewScenario(
                    scenario_id=uuid7(),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    preview_session_id=preview_session_id,
                    scenario=scenario,
                    role=role,
                    updated_by=principal_id,
                    lock_version=1,
                    created_at=now,
                    updated_at=now,
                )
                await uow.connection.execute(
                    frontend_preview_scenarios.insert().values(**record.model_dump())
                )
            else:
                result = await uow.connection.execute(
                    update(frontend_preview_scenarios)
                    .where(
                        frontend_preview_scenarios.c.scenario_id == row["scenario_id"]
                    )
                    .values(
                        scenario=scenario,
                        role=role,
                        updated_by=principal_id,
                        updated_at=now,
                        lock_version=frontend_preview_scenarios.c.lock_version + 1,
                    )
                    .returning(frontend_preview_scenarios)
                )
                record = FrontendPreviewScenario.model_validate(
                    dict(result.mappings().one())
                )
            await uow.commit()
        return record
