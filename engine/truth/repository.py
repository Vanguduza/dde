"""Async repository for Project Truth tables (Chapter 3.3, 3.8).

Every read and write here executes on the connection of an already-open
`PostgresUnitOfWork` (Chapter 3.5); this module never begins or ends a
transaction itself.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.edr import Edr
from engine.contracts.product_constitution_version import ProductConstitutionVersion
from engine.contracts.requirement import Requirement
from engine.truth.tables import edrs, product_constitution_versions, requirements


class TruthRepository:
    """Reads and writes rows for the three Chapter 3.3 Project Truth tables."""

    async def insert_constitution(
        self, connection: AsyncConnection, record: ProductConstitutionVersion
    ) -> None:
        await connection.execute(
            product_constitution_versions.insert().values(**record.model_dump())
        )

    async def update_constitution_status(
        self,
        connection: AsyncConnection,
        version_id: UUID,
        *,
        status: str,
        updated_at: datetime,
    ) -> None:
        await connection.execute(
            product_constitution_versions.update()
            .where(product_constitution_versions.c.version_id == version_id)
            .values(status=status, updated_at=updated_at)
        )

    async def get_active_constitution(
        self, connection: AsyncConnection, project_id: UUID
    ) -> ProductConstitutionVersion | None:
        result = await connection.execute(
            select(product_constitution_versions)
            .where(
                product_constitution_versions.c.project_id == project_id,
                product_constitution_versions.c.status == "active",
            )
            .order_by(product_constitution_versions.c.version.desc())
            .limit(1)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return ProductConstitutionVersion.model_validate(dict(row))

    async def get_requirement(
        self, connection: AsyncConnection, requirement_id: UUID
    ) -> Requirement | None:
        result = await connection.execute(
            select(requirements).where(requirements.c.requirement_id == requirement_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return Requirement.model_validate(dict(row))

    async def get_requirement_by_slug(
        self, connection: AsyncConnection, project_id: UUID, slug: str
    ) -> Requirement | None:
        result = await connection.execute(
            select(requirements).where(
                requirements.c.project_id == project_id,
                requirements.c.slug == slug,
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return Requirement.model_validate(dict(row))

    async def insert_requirement(
        self, connection: AsyncConnection, record: Requirement
    ) -> None:
        await connection.execute(requirements.insert().values(**record.model_dump()))

    async def update_requirement_status(
        self,
        connection: AsyncConnection,
        requirement_id: UUID,
        *,
        status: str,
        updated_at: datetime,
    ) -> None:
        await connection.execute(
            requirements.update()
            .where(requirements.c.requirement_id == requirement_id)
            .values(status=status, updated_at=updated_at)
        )

    async def get_edr(self, connection: AsyncConnection, edr_id: UUID) -> Edr | None:
        result = await connection.execute(select(edrs).where(edrs.c.edr_id == edr_id))
        row = result.mappings().first()
        if row is None:
            return None
        return Edr.model_validate(dict(row))

    async def get_edr_by_slug(
        self, connection: AsyncConnection, project_id: UUID, slug: str
    ) -> Edr | None:
        result = await connection.execute(
            select(edrs).where(edrs.c.project_id == project_id, edrs.c.slug == slug)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return Edr.model_validate(dict(row))

    async def insert_edr(self, connection: AsyncConnection, record: Edr) -> None:
        await connection.execute(edrs.insert().values(**record.model_dump()))

    async def update_edr_status(
        self,
        connection: AsyncConnection,
        edr_id: UUID,
        *,
        status: str,
        updated_at: datetime,
        decided_by_principal: UUID | None = None,
        decided_at: datetime | None = None,
    ) -> None:
        values: dict[str, object] = {"status": status, "updated_at": updated_at}
        if decided_by_principal is not None:
            values["decided_by_principal"] = decided_by_principal
        if decided_at is not None:
            values["decided_at"] = decided_at
        await connection.execute(
            edrs.update().where(edrs.c.edr_id == edr_id).values(**values)
        )

    async def update_edr_content(
        self,
        connection: AsyncConnection,
        edr_id: UUID,
        *,
        decision: str,
        updated_at: datetime,
    ) -> None:
        """Revise decision content. Callers must first confirm the row is
        still `proposed` (Chapter 2.2 rank 4) — this method performs no
        status check itself and is not part of the public API surface."""
        await connection.execute(
            edrs.update()
            .where(edrs.c.edr_id == edr_id)
            .values(decision=decision, updated_at=updated_at)
        )
