"""Async repository for the Chapter 4.3 registry tables (Chapter 3.3,
3.8).

Every read and write executes on the connection of an already-open
`PostgresUnitOfWork`; this module never begins or ends a transaction.
JSONB container values are JSON-safe re-serialised before binding, the
same shape `engine.invariants.repository` uses for its JSONB columns.
"""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.mission_template import MissionTemplate
from engine.contracts.plan_draft import PlanDraft, Refusal
from engine.planning.registry_tables import mission_templates, plan_drafts

_TEMPLATE_JSONB_FIELDS = ("nodes", "edges")
_DRAFT_JSONB_FIELDS = ("nodes", "edges", "refusals")


def _json_safe(value: object) -> object:
    def _default(item: object) -> object:
        if hasattr(item, "model_dump"):
            return item.model_dump(mode="json")
        return str(item)

    if isinstance(value, (list, dict)):
        return json.loads(json.dumps(value, default=_default))
    return value


def _values(
    record: MissionTemplate | PlanDraft, jsonb_fields: tuple[str, ...]
) -> dict[str, object]:
    dumped = record.model_dump()
    for field in jsonb_fields:
        dumped[field] = _json_safe(dumped[field])
    return dumped


class PlanningRegistryRepository:
    """Reads and writes rows for `mission_templates` and `plan_drafts`."""

    async def insert_template(
        self, connection: AsyncConnection, record: MissionTemplate
    ) -> None:
        await connection.execute(
            mission_templates.insert().values(**_values(record, _TEMPLATE_JSONB_FIELDS))
        )

    async def get_template(
        self, connection: AsyncConnection, template_id: UUID
    ) -> MissionTemplate | None:
        result = await connection.execute(
            select(mission_templates).where(
                mission_templates.c.template_id == template_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return MissionTemplate.model_validate(dict(row))

    async def get_template_by_version(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        template_key: str,
        template_version: str,
    ) -> MissionTemplate | None:
        """Definitions are immutable and content-hashed (Chapter 3.10): a
        second `register()` with identical definition fields must find the
        existing row rather than mint a duplicate."""
        result = await connection.execute(
            select(mission_templates).where(
                mission_templates.c.project_id == project_id,
                mission_templates.c.template_key == template_key,
                mission_templates.c.template_version == template_version,
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return MissionTemplate.model_validate(dict(row))

    async def list_active_for_project(
        self, connection: AsyncConnection, project_id: UUID
    ) -> list[MissionTemplate]:
        result = await connection.execute(
            select(mission_templates).where(
                mission_templates.c.project_id == project_id,
                mission_templates.c.status == "ACTIVE",
            )
        )
        return [
            MissionTemplate.model_validate(dict(row)) for row in result.mappings().all()
        ]

    async def update_template_status(
        self,
        connection: AsyncConnection,
        template_id: UUID,
        *,
        status: str,
        updated_at: object,
    ) -> None:
        await connection.execute(
            mission_templates.update()
            .where(mission_templates.c.template_id == template_id)
            .values(status=status, updated_at=updated_at)
        )

    # --- drafts ---------------------------------------------------------

    async def insert_draft(
        self, connection: AsyncConnection, record: PlanDraft
    ) -> None:
        await connection.execute(
            plan_drafts.insert().values(**_values(record, _DRAFT_JSONB_FIELDS))
        )

    async def get_draft(
        self, connection: AsyncConnection, draft_id: UUID
    ) -> PlanDraft | None:
        result = await connection.execute(
            select(plan_drafts).where(plan_drafts.c.draft_id == draft_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return PlanDraft.model_validate(dict(row))

    async def get_draft_by_provenance(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        project_id: UUID,
        provenance_key: str,
    ) -> PlanDraft | None:
        result = await connection.execute(
            select(plan_drafts).where(
                plan_drafts.c.tenant_id == tenant_id,
                plan_drafts.c.project_id == project_id,
                plan_drafts.c.provenance_key == provenance_key,
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return PlanDraft.model_validate(dict(row))

    async def update_draft(
        self,
        connection: AsyncConnection,
        draft_id: UUID,
        *,
        status: str,
        refusals: list[Refusal],
        promoted_graph_id: UUID | None,
        updated_at: object,
    ) -> None:
        await connection.execute(
            plan_drafts.update()
            .where(plan_drafts.c.draft_id == draft_id)
            .values(
                status=status,
                refusals=[refusal.model_dump(mode="json") for refusal in refusals],
                promoted_graph_id=promoted_graph_id,
                updated_at=updated_at,
            )
        )
