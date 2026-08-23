"""Async repository for Chapter 11.6 tables (Chapter 3.3, 3.8).

Every read and write executes on the connection of an already-open
`PostgresUnitOfWork`; this module never begins or ends a transaction.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.product_environment import ProductEnvironment
from engine.contracts.seed_dataset import SeedDataset
from engine.product_env.tables import product_environments, seed_datasets


class ProductEnvRepository:
    """Reads and writes rows for the two Chapter 11.6 tables."""

    async def insert_product_environment(
        self, connection: AsyncConnection, record: ProductEnvironment
    ) -> None:
        await connection.execute(
            product_environments.insert().values(**record.model_dump(by_alias=True))
        )

    async def get_product_environment(
        self, connection: AsyncConnection, product_env_id: UUID
    ) -> ProductEnvironment | None:
        result = await connection.execute(
            select(product_environments).where(
                product_environments.c.product_env_id == product_env_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return ProductEnvironment.model_validate(dict(row))

    async def find_by_idempotency_key(
        self,
        connection: AsyncConnection,
        tenant_id: UUID,
        project_id: UUID,
        idempotency_key: str,
    ) -> ProductEnvironment | None:
        result = await connection.execute(
            select(product_environments).where(
                product_environments.c.tenant_id == tenant_id,
                product_environments.c.project_id == project_id,
                product_environments.c.idempotency_key == idempotency_key,
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return ProductEnvironment.model_validate(dict(row))

    async def update_lifecycle(
        self,
        connection: AsyncConnection,
        product_env_id: UUID,
        *,
        status: str | None = None,
        migration_state: str | None = None,
        migration_verification: dict[str, object] | None = None,
        seed_dataset_id: UUID | None = None,
        base_url: str | None = None,
        failure_snapshot: dict[str, object] | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        values: dict[str, object] = {}
        if status is not None:
            values["status"] = status
        if migration_state is not None:
            values["migration_state"] = migration_state
        if migration_verification is not None:
            values["migration_verification"] = migration_verification
        if seed_dataset_id is not None:
            values["seed_dataset_id"] = seed_dataset_id
        if base_url is not None:
            values["base_url"] = base_url
        if failure_snapshot is not None:
            values["failure_snapshot"] = failure_snapshot
        if updated_at is not None:
            values["updated_at"] = updated_at
        await connection.execute(
            update(product_environments)
            .where(product_environments.c.product_env_id == product_env_id)
            .values(**values)
        )

    async def list_expired_not_terminal(
        self,
        connection: AsyncConnection,
        *,
        now: datetime,
        env_class: str,
    ) -> list[ProductEnvironment]:
        result = await connection.execute(
            select(product_environments).where(
                product_environments.c["class"] == env_class,
                product_environments.c.ttl_expires_at.is_not(None),
                product_environments.c.ttl_expires_at <= now,
                product_environments.c.status.notin_(("TEARDOWN", "FAILED")),
            )
        )
        return [
            ProductEnvironment.model_validate(dict(row))
            for row in result.mappings().all()
        ]

    async def insert_seed_dataset(
        self, connection: AsyncConnection, record: SeedDataset
    ) -> None:
        await connection.execute(seed_datasets.insert().values(**record.model_dump()))

    async def get_seed_dataset(
        self, connection: AsyncConnection, dataset_id: UUID
    ) -> SeedDataset | None:
        result = await connection.execute(
            select(seed_datasets).where(seed_datasets.c.dataset_id == dataset_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return SeedDataset.model_validate(dict(row))

    async def find_seed_dataset(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        project_id: UUID,
        slug: str,
        content_hash: str,
    ) -> SeedDataset | None:
        result = await connection.execute(
            select(seed_datasets).where(
                seed_datasets.c.tenant_id == tenant_id,
                seed_datasets.c.project_id == project_id,
                seed_datasets.c.slug == slug,
                seed_datasets.c.content_hash == content_hash,
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return SeedDataset.model_validate(dict(row))
