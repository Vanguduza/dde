"""Async repository for `workspaces` (Chapter 3.3, 3.8).

Every read and write here executes on the connection of an already-open
unit of work (Chapter 3.5); this module never begins or ends a transaction
itself.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.workspace import Workspace
from engine.workspaces.tables import workspaces


class WorkspaceRepository:
    """Reads and writes rows for `workspaces` — the Chapter 3.8 table owned
    by `engine.workspaces`."""

    async def insert_workspace(
        self, connection: AsyncConnection, record: Workspace
    ) -> None:
        await connection.execute(workspaces.insert().values(**record.model_dump()))

    async def get_workspace(
        self, connection: AsyncConnection, workspace_id: UUID
    ) -> Workspace | None:
        result = await connection.execute(
            select(workspaces).where(workspaces.c.workspace_id == workspace_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return Workspace.model_validate(dict(row))

    async def update_workspace(
        self,
        connection: AsyncConnection,
        workspace_id: UUID,
        *,
        expected_lock_version: int,
        updated_at: datetime,
        fields: dict[str, Any],
    ) -> int:
        """Optimistic-lock update (Chapter 3.5): the `WHERE lock_version =
        expected` clause is what makes a stale concurrent write affect zero
        rows instead of silently overwriting a newer one."""
        result = await connection.execute(
            workspaces.update()
            .where(
                workspaces.c.workspace_id == workspace_id,
                workspaces.c.lock_version == expected_lock_version,
            )
            .values(
                **fields,
                lock_version=workspaces.c.lock_version + 1,
                updated_at=updated_at,
            )
        )
        return int(result.rowcount)
