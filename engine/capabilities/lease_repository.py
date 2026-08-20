"""Async repository for `capability_leases` (Chapter 3.3, 3.8) -- owned
solely by `engine.capabilities`. Mirrors `engine.capabilities.repository`'s
`_json_safe` convention for the same reason: `model_dump()` leaves `UUID`
values nested inside the `resource_scope`/`constraints` JSONB columns as
non-JSON-serialisable objects.
"""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.capabilities.lease_tables import capability_leases
from engine.contracts.capability_lease import CapabilityLease

_JSONB_FIELDS = ("resource_scope", "constraints")


def _json_safe(value: object) -> object:
    if isinstance(value, (list, dict)):
        return json.loads(json.dumps(value, default=str))
    return value


def _values(record: CapabilityLease) -> dict[str, object]:
    dumped = record.model_dump()
    for field in _JSONB_FIELDS:
        dumped[field] = _json_safe(dumped[field])
    return dumped


class CapabilityLeaseRepository:
    """Reads and writes rows for `capability_leases`."""

    async def insert_lease(
        self, connection: AsyncConnection, record: CapabilityLease
    ) -> None:
        await connection.execute(capability_leases.insert().values(**_values(record)))

    async def update_fields(
        self,
        connection: AsyncConnection,
        lease_id: UUID,
        *,
        fields: dict[str, object],
    ) -> int:
        safe_fields = {name: _json_safe(value) for name, value in fields.items()}
        result = await connection.execute(
            capability_leases.update()
            .where(capability_leases.c.lease_id == lease_id)
            .values(**safe_fields)
        )
        return result.rowcount

    async def get_by_id(
        self, connection: AsyncConnection, lease_id: UUID
    ) -> CapabilityLease | None:
        result = await connection.execute(
            select(capability_leases).where(capability_leases.c.lease_id == lease_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return CapabilityLease.model_validate(dict(row))

    async def get_by_hash(
        self, connection: AsyncConnection, lease_hash: str
    ) -> CapabilityLease | None:
        """Idempotency support: a re-request of the identical definition
        (Chapter 3.10) finds its own prior row rather than minting a
        duplicate."""
        result = await connection.execute(
            select(capability_leases)
            .where(capability_leases.c.lease_hash == lease_hash)
            .order_by(capability_leases.c.created_at.asc())
        )
        row = result.mappings().first()
        if row is None:
            return None
        return CapabilityLease.model_validate(dict(row))

    async def get_active_for_run(
        self,
        connection: AsyncConnection,
        *,
        worker_run_id: UUID,
        capability_id: str,
    ) -> CapabilityLease | None:
        """The lease `require_active`'s enforcement guard checks: the most
        recently issued lease bound to this run for this capability. Most
        recent, not "the only one", because a run may legitimately request
        the same capability more than once across its lifetime (e.g. after
        a denial is corrected) -- Chapter 9.2 never says a run holds at
        most one lease per capability."""
        result = await connection.execute(
            select(capability_leases)
            .where(
                capability_leases.c.worker_run_id == worker_run_id,
                capability_leases.c.capability_id == capability_id,
            )
            .order_by(capability_leases.c.created_at.desc())
        )
        row = result.mappings().first()
        if row is None:
            return None
        return CapabilityLease.model_validate(dict(row))

    async def list_for_run(
        self, connection: AsyncConnection, worker_run_id: UUID
    ) -> list[CapabilityLease]:
        result = await connection.execute(
            select(capability_leases)
            .where(capability_leases.c.worker_run_id == worker_run_id)
            .order_by(capability_leases.c.created_at.asc())
        )
        return [
            CapabilityLease.model_validate(dict(row)) for row in result.mappings().all()
        ]
