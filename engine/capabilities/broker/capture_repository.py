"""Async repository for captured provider credentials + broker vault rows."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.capabilities.broker.capture_tables import (
    broker_static_secret_material,
    captured_provider_credentials,
)
from engine.contracts.captured_provider_credential import CapturedProviderCredential


def _values(record: CapturedProviderCredential) -> dict[str, object]:
    return record.model_dump(mode="python")


class CapturedCredentialRepository:
    """Reads/writes captured metadata and the broker-private vault table."""

    async def insert_capture(
        self, connection: AsyncConnection, record: CapturedProviderCredential
    ) -> None:
        await connection.execute(
            captured_provider_credentials.insert().values(**_values(record))
        )

    async def update_capture(
        self,
        connection: AsyncConnection,
        capture_id: UUID,
        *,
        status: str,
        superseded_by_capture_id: UUID | None = None,
        revoked_at: datetime | None = None,
        updated_at: datetime,
    ) -> None:
        values: dict[str, object] = {
            "status": status,
            "updated_at": updated_at,
        }
        if superseded_by_capture_id is not None:
            values["superseded_by_capture_id"] = superseded_by_capture_id
        if revoked_at is not None:
            values["revoked_at"] = revoked_at
        await connection.execute(
            captured_provider_credentials.update()
            .where(captured_provider_credentials.c.capture_id == capture_id)
            .values(**values)
        )

    async def get_capture(
        self, connection: AsyncConnection, capture_id: UUID
    ) -> CapturedProviderCredential | None:
        result = await connection.execute(
            select(captured_provider_credentials).where(
                captured_provider_credentials.c.capture_id == capture_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return CapturedProviderCredential.model_validate(dict(row))

    async def get_active_capture(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        project_id: UUID,
        provider_id: str,
    ) -> CapturedProviderCredential | None:
        result = await connection.execute(
            select(captured_provider_credentials)
            .where(
                captured_provider_credentials.c.tenant_id == tenant_id,
                captured_provider_credentials.c.project_id == project_id,
                captured_provider_credentials.c.provider_id == provider_id,
                captured_provider_credentials.c.status == "CAPTURED",
            )
            .order_by(captured_provider_credentials.c.captured_at.desc())
            .limit(1)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return CapturedProviderCredential.model_validate(dict(row))

    async def insert_secret(
        self,
        connection: AsyncConnection,
        *,
        capture_id: UUID,
        tenant_id: UUID,
        project_id: UUID,
        provider_id: str,
        secret_value: str,
        created_at: datetime,
    ) -> None:
        await connection.execute(
            broker_static_secret_material.insert().values(
                capture_id=capture_id,
                tenant_id=tenant_id,
                project_id=project_id,
                provider_id=provider_id,
                secret_value=secret_value,
                created_at=created_at,
            )
        )

    async def read_secret(
        self, connection: AsyncConnection, capture_id: UUID
    ) -> str | None:
        """Broker-only. Never call from Gateway response builders."""
        result = await connection.execute(
            select(broker_static_secret_material.c.secret_value).where(
                broker_static_secret_material.c.capture_id == capture_id
            )
        )
        row = result.first()
        if row is None:
            return None
        return str(row[0])

    async def delete_secret(
        self, connection: AsyncConnection, capture_id: UUID
    ) -> None:
        await connection.execute(
            broker_static_secret_material.delete().where(
                broker_static_secret_material.c.capture_id == capture_id
            )
        )
