"""Async repository for `capabilities` (Chapter 3.3, 3.8) -- owned solely by
`engine.capabilities`.

Every read and write here executes on the connection of an already-open unit
of work (Chapter 3.5); this module never begins or ends a transaction
itself. Follows `engine.verification.repository`'s `_json_safe` convention:
`model_dump()` (default "python" mode) is required for the plain `Uuid`/
`TIMESTAMP` columns, but leaves `UUID`/`datetime` values nested inside the
JSONB list/dict columns as non-JSON-serialisable objects, so those columns
are re-serialised before binding.
"""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.capabilities.tables import capabilities
from engine.contracts.capability_descriptor import CapabilityDescriptor

_JSONB_FIELDS = (
    "implementations",
    "supported_worker_profiles",
    "supported_environments",
    "supported_workloads",
    "permission_model",
    "cost_model",
    "network_requirements",
    "dependencies",
    "provenance",
)


def _json_safe(value: object) -> object:
    if isinstance(value, (list, dict)):
        return json.loads(json.dumps(value, default=str))
    return value


def _values(record: CapabilityDescriptor) -> dict[str, object]:
    dumped = record.model_dump()
    for field in _JSONB_FIELDS:
        dumped[field] = _json_safe(dumped[field])
    return dumped


class CapabilityRepository:
    """Reads and writes rows for `capabilities`."""

    async def insert_descriptor(
        self, connection: AsyncConnection, record: CapabilityDescriptor
    ) -> None:
        await connection.execute(capabilities.insert().values(**_values(record)))

    async def update_fields(
        self,
        connection: AsyncConnection,
        descriptor_id: UUID,
        *,
        fields: dict[str, object],
    ) -> int:
        safe_fields = {name: _json_safe(value) for name, value in fields.items()}
        result = await connection.execute(
            capabilities.update()
            .where(capabilities.c.descriptor_id == descriptor_id)
            .values(**safe_fields)
        )
        return result.rowcount

    async def get_by_id(
        self, connection: AsyncConnection, descriptor_id: UUID
    ) -> CapabilityDescriptor | None:
        result = await connection.execute(
            select(capabilities).where(capabilities.c.descriptor_id == descriptor_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return CapabilityDescriptor.model_validate(dict(row))

    async def get_by_capability_and_version(
        self, connection: AsyncConnection, capability_id: str, version: str
    ) -> CapabilityDescriptor | None:
        """Chapter 3.10: definitions are immutable and content-hashed; a
        second `register()` call for the same `(capability_id, version)`
        must find the existing row rather than mint a duplicate."""
        result = await connection.execute(
            select(capabilities).where(
                capabilities.c.capability_id == capability_id,
                capabilities.c.version == version,
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return CapabilityDescriptor.model_validate(dict(row))

    async def get_active_by_capability_id(
        self, connection: AsyncConnection, capability_id: str
    ) -> CapabilityDescriptor | None:
        """The one `ACTIVE` version of a given `capability_id`, if any --
        `register()` uses this to decide what a new version supersedes."""
        result = await connection.execute(
            select(capabilities).where(
                capabilities.c.capability_id == capability_id,
                capabilities.c.lifecycle_status == "ACTIVE",
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return CapabilityDescriptor.model_validate(dict(row))

    async def list_versions(
        self, connection: AsyncConnection, capability_id: str
    ) -> list[CapabilityDescriptor]:
        result = await connection.execute(
            select(capabilities)
            .where(capabilities.c.capability_id == capability_id)
            .order_by(capabilities.c.created_at.asc())
        )
        return [
            CapabilityDescriptor.model_validate(dict(row))
            for row in result.mappings().all()
        ]

    async def list_by_category(
        self, connection: AsyncConnection, category: str
    ) -> list[CapabilityDescriptor]:
        result = await connection.execute(
            select(capabilities)
            .where(capabilities.c.category == category)
            .order_by(capabilities.c.created_at.asc())
        )
        return [
            CapabilityDescriptor.model_validate(dict(row))
            for row in result.mappings().all()
        ]
