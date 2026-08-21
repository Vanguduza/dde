"""Async repositories for Chapter 13 governance tables."""

from __future__ import annotations

import json
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.approval import Approval
from engine.contracts.attention_item import AttentionItem
from engine.contracts.standing_approval import StandingApproval
from engine.governance.tables import approvals, attention_items, standing_approvals

_APPROVAL_JSONB = ("evidence_refs",)
_STANDING_JSONB = ("approval_types", "path_scope", "forbidden_operations")


def _json_safe(value: object) -> object:
    if isinstance(value, (list, dict)):
        return json.loads(json.dumps(value, default=str))
    return value


def _row(payload: dict[str, object]) -> dict[str, object]:
    converted = dict(payload)
    for field in ("human_minutes", "cost_ceiling", "cost_used"):
        value = converted.get(field)
        if isinstance(value, Decimal):
            converted[field] = float(value)
    return converted


def _values(
    record: Approval | StandingApproval, json_fields: tuple[str, ...]
) -> dict[str, object]:
    dumped = record.model_dump()
    for field in json_fields:
        dumped[field] = _json_safe(dumped[field])
    return dumped


class ApprovalRepository:
    async def insert(self, connection: AsyncConnection, record: Approval) -> None:
        await connection.execute(
            approvals.insert().values(**_values(record, _APPROVAL_JSONB))
        )

    async def update_fields(
        self,
        connection: AsyncConnection,
        approval_id: UUID,
        *,
        fields: dict[str, object],
    ) -> int:
        safe = {name: _json_safe(value) for name, value in fields.items()}
        result = await connection.execute(
            approvals.update()
            .where(approvals.c.approval_id == approval_id)
            .values(**safe)
        )
        return int(result.rowcount)

    async def get_by_id(
        self, connection: AsyncConnection, approval_id: UUID
    ) -> Approval | None:
        result = await connection.execute(
            select(approvals).where(approvals.c.approval_id == approval_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return Approval.model_validate(_row(dict(row)))

    async def get_by_scope_hash(
        self, connection: AsyncConnection, scope_hash: str
    ) -> Approval | None:
        result = await connection.execute(
            select(approvals)
            .where(approvals.c.scope_hash == scope_hash)
            .order_by(approvals.c.created_at.desc())
        )
        row = result.mappings().first()
        if row is None:
            return None
        return Approval.model_validate(_row(dict(row)))

    async def get_approved_by_scope_hash(
        self,
        connection: AsyncConnection,
        scope_hash: str,
        approval_type: str,
    ) -> Approval | None:
        result = await connection.execute(
            select(approvals)
            .where(
                approvals.c.scope_hash == scope_hash,
                approvals.c.approval_type == approval_type,
                approvals.c.status == "APPROVED",
            )
            .order_by(approvals.c.created_at.desc())
        )
        row = result.mappings().first()
        if row is None:
            return None
        return Approval.model_validate(_row(dict(row)))

    async def list_for_mission(
        self, connection: AsyncConnection, mission_id: UUID
    ) -> list[Approval]:
        result = await connection.execute(
            select(approvals)
            .where(approvals.c.mission_id == mission_id)
            .order_by(approvals.c.created_at.asc())
        )
        return [
            Approval.model_validate(_row(dict(row))) for row in result.mappings().all()
        ]


class StandingApprovalRepository:
    async def insert(
        self, connection: AsyncConnection, record: StandingApproval
    ) -> None:
        await connection.execute(
            standing_approvals.insert().values(**_values(record, _STANDING_JSONB))
        )

    async def update_fields(
        self,
        connection: AsyncConnection,
        standing_id: UUID,
        *,
        fields: dict[str, object],
    ) -> int:
        safe = {name: _json_safe(value) for name, value in fields.items()}
        result = await connection.execute(
            standing_approvals.update()
            .where(standing_approvals.c.standing_id == standing_id)
            .values(**safe)
        )
        return int(result.rowcount)

    async def get_by_id(
        self, connection: AsyncConnection, standing_id: UUID
    ) -> StandingApproval | None:
        result = await connection.execute(
            select(standing_approvals).where(
                standing_approvals.c.standing_id == standing_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return StandingApproval.model_validate(_row(dict(row)))

    async def list_active_for_project(
        self, connection: AsyncConnection, project_id: UUID
    ) -> list[StandingApproval]:
        result = await connection.execute(
            select(standing_approvals)
            .where(
                standing_approvals.c.project_id == project_id,
                standing_approvals.c.status == "ACTIVE",
            )
            .order_by(standing_approvals.c.created_at.asc())
        )
        return [
            StandingApproval.model_validate(_row(dict(row)))
            for row in result.mappings().all()
        ]


class AttentionItemRepository:
    async def insert(self, connection: AsyncConnection, record: AttentionItem) -> None:
        await connection.execute(attention_items.insert().values(**record.model_dump()))

    async def update_fields(
        self,
        connection: AsyncConnection,
        attention_id: UUID,
        *,
        fields: dict[str, object],
    ) -> int:
        result = await connection.execute(
            attention_items.update()
            .where(attention_items.c.attention_id == attention_id)
            .values(**fields)
        )
        return int(result.rowcount)

    async def get_by_id(
        self, connection: AsyncConnection, attention_id: UUID
    ) -> AttentionItem | None:
        result = await connection.execute(
            select(attention_items).where(
                attention_items.c.attention_id == attention_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return AttentionItem.model_validate(dict(row))

    async def list_for_mission(
        self, connection: AsyncConnection, mission_id: UUID
    ) -> list[AttentionItem]:
        result = await connection.execute(
            select(attention_items)
            .where(attention_items.c.mission_id == mission_id)
            .order_by(attention_items.c.opened_at.asc())
        )
        return [
            AttentionItem.model_validate(dict(row)) for row in result.mappings().all()
        ]
