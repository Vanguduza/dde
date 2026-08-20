"""Async repository for `credential_handles` (Chapter 3.3, 3.8) -- owned
solely by `engine.capabilities.broker`. Mirrors `engine.capabilities.
lease_repository`'s `_json_safe` convention: `model_dump()` leaves `UUID`
values nested inside the `resource_scope` JSONB column non-JSON-serialisable.
"""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.capabilities.broker.tables import credential_handles
from engine.contracts.credential_handle import CredentialHandle

_JSONB_FIELDS = ("resource_scope",)


def _json_safe(value: object) -> object:
    if isinstance(value, (list, dict)):
        return json.loads(json.dumps(value, default=str))
    return value


def _values(record: CredentialHandle) -> dict[str, object]:
    dumped = record.model_dump()
    for field in _JSONB_FIELDS:
        dumped[field] = _json_safe(dumped[field])
    return dumped


class CredentialHandleRepository:
    """Reads and writes rows for `credential_handles`."""

    async def insert_handle(
        self, connection: AsyncConnection, record: CredentialHandle
    ) -> None:
        await connection.execute(credential_handles.insert().values(**_values(record)))

    async def update_fields(
        self,
        connection: AsyncConnection,
        handle_id: UUID,
        *,
        fields: dict[str, object],
    ) -> int:
        safe_fields = {name: _json_safe(value) for name, value in fields.items()}
        result = await connection.execute(
            credential_handles.update()
            .where(credential_handles.c.handle_id == handle_id)
            .values(**safe_fields)
        )
        return result.rowcount

    async def get_by_id(
        self, connection: AsyncConnection, handle_id: UUID
    ) -> CredentialHandle | None:
        result = await connection.execute(
            select(credential_handles).where(
                credential_handles.c.handle_id == handle_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return CredentialHandle.model_validate(dict(row))

    async def list_for_lease(
        self, connection: AsyncConnection, lease_id: UUID
    ) -> list[CredentialHandle]:
        result = await connection.execute(
            select(credential_handles)
            .where(credential_handles.c.lease_id == lease_id)
            .order_by(credential_handles.c.created_at.asc())
        )
        return [
            CredentialHandle.model_validate(dict(row))
            for row in result.mappings().all()
        ]

    async def list_live_in_scope(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID | None = None,
        worker_run_id: UUID | None = None,
    ) -> list[CredentialHandle]:
        """`emergency_revoke`'s candidate set: every still-`ISSUED` handle
        under a tenant/project, optionally narrowed to one mission and/or
        one run (Chapter 14.3: "revokes all active material under a
        tenant/project/mission/run scope")."""
        clauses = [
            credential_handles.c.tenant_id == tenant_id,
            credential_handles.c.project_id == project_id,
            credential_handles.c.status == "ISSUED",
        ]
        if mission_id is not None:
            clauses.append(credential_handles.c.mission_id == mission_id)
        if worker_run_id is not None:
            clauses.append(credential_handles.c.worker_run_id == worker_run_id)
        result = await connection.execute(
            select(credential_handles)
            .where(*clauses)
            .order_by(credential_handles.c.created_at.asc())
        )
        return [
            CredentialHandle.model_validate(dict(row))
            for row in result.mappings().all()
        ]
