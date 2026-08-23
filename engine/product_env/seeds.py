"""Versioned, content-hashed seed dataset registry (Chapter 11.6).

"Seed datasets are versioned artifacts with content hashes, so an
invariant failure is reproducible." A dataset is immutable once ACTIVE;
a changed payload is a new version superseding the old one (Chapter
3.10's supersession pattern), never an overwrite.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.seed_dataset import SeedDataset
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.hashing import sha256_hex
from engine.core.ids import uuid7
from engine.product_env.repository import ProductEnvRepository
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")


class SeedRegistry:
    """Registers and resolves seed datasets inside a caller-supplied unit
    of work or its own."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: ProductEnvRepository | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or ProductEnvRepository()
        self._clock = clock or SystemClock()

    async def _run(
        self,
        uow: PostgresUnitOfWork | None,
        tenant_id: UUID,
        project_id: UUID,
        body: Callable[[PostgresUnitOfWork], Awaitable[T]],
    ) -> T:
        if uow is not None:
            return await body(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as owned:
            result = await body(owned)
            await owned.commit()
            return result

    async def register(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        slug: str,
        artifact_ref: str,
        created_by: str,
        supersedes_dataset_id: UUID | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> SeedDataset:
        """Register a new version of ``slug``.

        The content hash covers the seed payload reference and slug so two
        registrations with identical content collapse onto one row.
        """

        async def _op(active: PostgresUnitOfWork) -> SeedDataset:
            content_hash = sha256_hex(f"{slug}:{artifact_ref}")
            existing = await self._repository.find_seed_dataset(
                active.connection,
                tenant_id=tenant_id,
                project_id=project_id,
                slug=slug,
                content_hash=content_hash,
            )
            if existing is not None:
                return existing
            record = SeedDataset(
                dataset_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                slug=slug,
                version=1,
                content_hash=content_hash,
                artifact_ref=artifact_ref,
                supersedes_dataset_id=supersedes_dataset_id,
                status="ACTIVE",
                created_by=created_by,
                created_at=self._clock.now(),
            )
            await self._repository.insert_seed_dataset(active.connection, record)
            return record

        return await self._run(uow, tenant_id, project_id, _op)

    async def get(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        dataset_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> SeedDataset:
        async def _op(active: PostgresUnitOfWork) -> SeedDataset:
            record = await self._repository.get_seed_dataset(
                active.connection, dataset_id
            )
            if record is None:
                raise DdeError("POLICY_DENIED", "Unknown seed dataset")
            return record

        return await self._run(uow, tenant_id, project_id, _op)
