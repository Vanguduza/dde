"""Async repository for `checkpoints` (Chapter 12.1) -- owned solely by
`engine.recovery`.
"""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.checkpoint import Checkpoint
from engine.recovery.tables import checkpoints

_JSONB_UUID_LISTS = ("artifact_refs", "lease_refs")
_JSONB_STR_LISTS = (
    "completed_work",
    "verified_work",
    "pending_work",
    "known_failures",
    "do_not_repeat",
)


def _json_safe(value: object) -> object:
    if isinstance(value, (list, dict)):
        return json.loads(json.dumps(value, default=str))
    return value


def _values(record: Checkpoint) -> dict[str, object]:
    dumped = record.model_dump()
    for field in (*_JSONB_UUID_LISTS, *_JSONB_STR_LISTS):
        dumped[field] = _json_safe(dumped[field])
    return dumped


class CheckpointRepository:
    """Reads and inserts rows for `checkpoints`. Append-only: no update."""

    async def insert_checkpoint(
        self, connection: AsyncConnection, record: Checkpoint
    ) -> None:
        await connection.execute(checkpoints.insert().values(**_values(record)))

    async def get_by_id(
        self, connection: AsyncConnection, checkpoint_id: UUID
    ) -> Checkpoint | None:
        result = await connection.execute(
            select(checkpoints).where(checkpoints.c.checkpoint_id == checkpoint_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return Checkpoint.model_validate(dict(row))

    async def list_for_attempt(
        self, connection: AsyncConnection, task_attempt_id: UUID
    ) -> list[Checkpoint]:
        result = await connection.execute(
            select(checkpoints)
            .where(checkpoints.c.task_attempt_id == task_attempt_id)
            .order_by(checkpoints.c.created_at.asc())
        )
        return [Checkpoint.model_validate(dict(row)) for row in result.mappings().all()]

    async def list_for_mission(
        self, connection: AsyncConnection, mission_id: UUID
    ) -> list[Checkpoint]:
        result = await connection.execute(
            select(checkpoints)
            .where(checkpoints.c.mission_id == mission_id)
            .order_by(checkpoints.c.created_at.asc())
        )
        return [Checkpoint.model_validate(dict(row)) for row in result.mappings().all()]

    async def list_for_task(
        self, connection: AsyncConnection, task_id: UUID
    ) -> list[Checkpoint]:
        result = await connection.execute(
            select(checkpoints)
            .where(checkpoints.c.task_id == task_id)
            .order_by(checkpoints.c.created_at.desc())
        )
        return [Checkpoint.model_validate(dict(row)) for row in result.mappings().all()]
