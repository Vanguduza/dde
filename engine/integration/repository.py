"""Async repositories for `write_scope_leases` and `integration_proposals`
(Chapter 3.3, 3.8) -- both owned by `engine.integration`.

Every read and write here executes on the connection of an already-open
unit of work (Chapter 3.5); this module never begins or ends a transaction
itself.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.integration_proposal import IntegrationProposal
from engine.contracts.write_scope_lease import WriteScopeLease
from engine.integration.tables import integration_proposals, write_scope_leases


class WriteScopeLeaseRepository:
    """Reads and writes rows for `write_scope_leases`."""

    async def insert_lease(
        self, connection: AsyncConnection, record: WriteScopeLease
    ) -> None:
        await connection.execute(
            write_scope_leases.insert().values(**record.model_dump())
        )

    async def get_lease(
        self, connection: AsyncConnection, lease_id: UUID
    ) -> WriteScopeLease | None:
        result = await connection.execute(
            select(write_scope_leases).where(write_scope_leases.c.lease_id == lease_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return WriteScopeLease.model_validate(dict(row))

    async def list_held_for_project(
        self, connection: AsyncConnection, project_id: UUID
    ) -> list[WriteScopeLease]:
        """Chapter 10.3's conflict check operates over every lease that is
        still genuinely held (`RESERVED` or `ACTIVE`) within one project --
        `RELEASED`/`EXPIRED` leases no longer constrain scheduling."""
        result = await connection.execute(
            select(write_scope_leases).where(
                write_scope_leases.c.project_id == project_id,
                write_scope_leases.c.status.in_(("RESERVED", "ACTIVE")),
            )
        )
        return [
            WriteScopeLease.model_validate(dict(row)) for row in result.mappings().all()
        ]

    async def list_held_for_task(
        self, connection: AsyncConnection, task_id: UUID
    ) -> list[WriteScopeLease]:
        result = await connection.execute(
            select(write_scope_leases).where(
                write_scope_leases.c.task_id == task_id,
                write_scope_leases.c.status.in_(("RESERVED", "ACTIVE")),
            )
        )
        return [
            WriteScopeLease.model_validate(dict(row)) for row in result.mappings().all()
        ]

    async def update_lease(
        self,
        connection: AsyncConnection,
        lease_id: UUID,
        *,
        fields: dict[str, Any],
    ) -> int:
        result = await connection.execute(
            write_scope_leases.update()
            .where(write_scope_leases.c.lease_id == lease_id)
            .values(**fields)
        )
        return int(result.rowcount)


class IntegrationProposalRepository:
    """Reads and writes rows for `integration_proposals`."""

    async def insert_proposal(
        self, connection: AsyncConnection, record: IntegrationProposal
    ) -> None:
        dumped = record.model_dump()
        dumped["changed_paths"] = list(dumped["changed_paths"])
        await connection.execute(integration_proposals.insert().values(**dumped))

    async def get_proposal(
        self, connection: AsyncConnection, proposal_id: UUID
    ) -> IntegrationProposal | None:
        result = await connection.execute(
            select(integration_proposals).where(
                integration_proposals.c.proposal_id == proposal_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return IntegrationProposal.model_validate(dict(row))

    async def update_proposal(
        self,
        connection: AsyncConnection,
        proposal_id: UUID,
        *,
        fields: dict[str, Any],
    ) -> int:
        safe_fields = dict(fields)
        if "changed_paths" in safe_fields:
            safe_fields["changed_paths"] = list(safe_fields["changed_paths"])
        result = await connection.execute(
            integration_proposals.update()
            .where(integration_proposals.c.proposal_id == proposal_id)
            .values(**safe_fields)
        )
        return int(result.rowcount)

    async def list_for_task(
        self, connection: AsyncConnection, task_id: UUID
    ) -> list[IntegrationProposal]:
        result = await connection.execute(
            select(integration_proposals)
            .where(integration_proposals.c.task_id == task_id)
            .order_by(integration_proposals.c.created_at.asc())
        )
        return [
            IntegrationProposal.model_validate(dict(row))
            for row in result.mappings().all()
        ]

    async def list_for_project(
        self, connection: AsyncConnection, project_id: UUID
    ) -> list[IntegrationProposal]:
        result = await connection.execute(
            select(integration_proposals)
            .where(integration_proposals.c.project_id == project_id)
            .order_by(integration_proposals.c.created_at.desc())
        )
        return [
            IntegrationProposal.model_validate(dict(row))
            for row in result.mappings().all()
        ]

    async def list_for_mission(
        self, connection: AsyncConnection, mission_id: UUID
    ) -> list[IntegrationProposal]:
        result = await connection.execute(
            select(integration_proposals)
            .where(integration_proposals.c.mission_id == mission_id)
            .order_by(integration_proposals.c.created_at.asc())
        )
        return [
            IntegrationProposal.model_validate(dict(row))
            for row in result.mappings().all()
        ]
