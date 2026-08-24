"""Postgres capture path: raw key never in events / public payloads."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from engine.capabilities.broker.capture import StaticSecretCaptureService
from engine.capabilities.broker.capture_hashing import secret_content_hash
from engine.core.ids import uuid7
from tests.support.db import new_engine, seed_tenant

RAW_KEY = "osk_postgres_capture_raw_key_value"
RAW_KEY_2 = "osk_postgres_capture_raw_key_value_v2"

_VAULT_DDL = """
CREATE TABLE IF NOT EXISTS broker_static_secret_material (
    capture_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    provider_id text NOT NULL,
    secret_value text NOT NULL,
    created_at timestamptz NOT NULL,
    PRIMARY KEY (capture_id)
);
"""


async def _ensure_vault(engine) -> None:
    async with engine.connect() as connection:
        await connection.execute(text(_VAULT_DDL))
        await connection.commit()


@pytest.mark.asyncio
async def test_capture_persists_hash_and_vault_not_in_event() -> None:
    engine = new_engine()
    await _ensure_vault(engine)
    fixture = await seed_tenant(engine)
    service = StaticSecretCaptureService(engine)

    result = await service.capture_opensandbox_api_key(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        api_key=RAW_KEY,
        domain="osb.example",
        captured_by=str(fixture.principal_id),
        idempotency_key=f"capture-{uuid7()}",
    )
    assert result.replayed is False
    assert result.record.secret_hash == secret_content_hash(RAW_KEY)
    assert RAW_KEY not in repr(result.record.model_dump(mode="json"))

    public = StaticSecretCaptureService.public_status(result.record)
    assert RAW_KEY not in repr(public)
    assert public["fingerprint"] == result.record.fingerprint

    async with engine.connect() as connection:
        await connection.execute(
            text(
                "SELECT set_config('dde.tenant_id', :t, false), "
                "set_config('dde.project_id', :p, false)"
            ),
            {"t": str(fixture.tenant_id), "p": str(fixture.project_id)},
        )
        event = (
            await connection.execute(
                text(
                    "SELECT payload FROM events "
                    "WHERE event_type = 'ProviderCredentialCaptured' "
                    "ORDER BY created_at DESC LIMIT 1"
                )
            )
        ).mappings().first()
        vault = (
            await connection.execute(
                text(
                    "SELECT secret_value FROM broker_static_secret_material "
                    "WHERE capture_id = :id"
                ),
                {"id": result.record.capture_id},
            )
        ).first()

    assert event is not None
    assert RAW_KEY not in repr(dict(event["payload"]))
    assert vault is not None
    assert vault[0] == RAW_KEY

    resolved = await service.resolve_secret(
        tenant_id=fixture.tenant_id, project_id=fixture.project_id
    )
    assert resolved == RAW_KEY
    await engine.dispose()


@pytest.mark.asyncio
async def test_recapture_supersedes_and_drops_old_vault() -> None:
    engine = new_engine()
    await _ensure_vault(engine)
    fixture = await seed_tenant(engine)
    service = StaticSecretCaptureService(engine)

    first = await service.capture_opensandbox_api_key(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        api_key=RAW_KEY,
        domain=None,
        captured_by=str(fixture.principal_id),
        idempotency_key=f"capture-a-{uuid7()}",
    )
    second = await service.capture_opensandbox_api_key(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        api_key=RAW_KEY_2,
        domain=None,
        captured_by=str(fixture.principal_id),
        idempotency_key=f"capture-b-{uuid7()}",
    )
    assert second.record.supersedes_capture_id == first.record.capture_id
    assert second.record.secret_hash == secret_content_hash(RAW_KEY_2)

    async with engine.connect() as connection:
        await connection.execute(
            text(
                "SELECT set_config('dde.tenant_id', :t, false), "
                "set_config('dde.project_id', :p, false)"
            ),
            {"t": str(fixture.tenant_id), "p": str(fixture.project_id)},
        )
        old_status = (
            await connection.execute(
                text(
                    "SELECT status FROM captured_provider_credentials "
                    "WHERE capture_id = :id"
                ),
                {"id": first.record.capture_id},
            )
        ).scalar_one()
        old_vault = (
            await connection.execute(
                text(
                    "SELECT 1 FROM broker_static_secret_material "
                    "WHERE capture_id = :id"
                ),
                {"id": first.record.capture_id},
            )
        ).first()

    assert old_status == "SUPERSEDED"
    assert old_vault is None
    await engine.dispose()
