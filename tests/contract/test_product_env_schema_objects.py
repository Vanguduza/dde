"""Chapter 19.1 schema/contract tests for the ProductEnvironment and
SeedDataset objects (Chapter 11.6).

Pins: valid minimal rows, unknown-field rejection, enum discipline on
`class`/`status`/`migration_state`, TTL required for ephemeral previews at
the contract boundary's service layer, content-hash presence on seed
datasets, generated-code drift (the generated SQL bundle must contain the
new tables), and Chapter 3.2 RLS emission for both new tables.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from engine.contracts.product_environment import ProductEnvironment
from engine.contracts.seed_dataset import SeedDataset
from engine.core.ids import uuid7

ROOT = Path(__file__).resolve().parents[2]
GENERATED_SQL = ROOT / "schemas" / "sql" / "0001_stage1.sql"


def _now() -> datetime:
    return datetime.now(UTC)


def _valid_product_env_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "product_env_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "mission_id": None,
        "class": "ephemeral_preview",
        "source_revision": "abc1234",
        "build_artifact_ref": "r2://artifacts/build.tar.gz",
        "runtime_topology_ref": {"compose": "docker-compose.yml"},
        "datastore_ref": "postgres://throwaway/db",
        "seed_dataset_id": None,
        "migration_state": "PENDING_BASELINE",
        "base_url": None,
        "credentials_profile_id": None,
        "status": "PROVISIONING",
        "ttl_expires_at": _now(),
        "idempotency_key": "product-env:provision:test-key",
        "created_at": _now(),
        "updated_at": _now(),
    }
    payload.update(overrides)
    return payload


def _valid_seed_dataset_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "dataset_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "slug": "erp-baseline",
        "version": 3,
        "content_hash": "deadbeef",
        "artifact_ref": "r2://seeds/erp-baseline-v3.sql",
        "supersedes_dataset_id": None,
        "status": "ACTIVE",
        "created_by": "principal-1",
        "created_at": _now(),
    }
    payload.update(overrides)
    return payload


def test_product_environment_valid_with_required_fields() -> None:
    record = ProductEnvironment.model_validate(_valid_product_env_payload())
    assert record.class_ == "ephemeral_preview"
    assert record.status == "PROVISIONING"
    assert record.ttl_expires_at is not None


def test_product_environment_rejects_unknown_fields() -> None:
    payload = _valid_product_env_payload(extra=True)
    with pytest.raises(ValidationError):
        ProductEnvironment.model_validate(payload)


def test_product_environment_rejects_unknown_class_value() -> None:
    with pytest.raises(ValidationError):
        ProductEnvironment.model_validate(_valid_product_env_payload(cls="sandbox"))


def test_product_environment_rejects_unknown_status_value() -> None:
    with pytest.raises(ValidationError):
        ProductEnvironment.model_validate(
            _valid_product_env_payload(status="DESTROYED")
        )


def test_product_environment_rejects_unknown_migration_state() -> None:
    with pytest.raises(ValidationError):
        ProductEnvironment.model_validate(
            _valid_product_env_payload(migration_state="WINGED_IT")
        )


def test_seed_dataset_is_content_hashed_and_versioned() -> None:
    record = SeedDataset.model_validate(_valid_seed_dataset_payload())
    assert record.content_hash
    assert record.version >= 1


def test_seed_dataset_rejects_missing_content_hash() -> None:
    payload = _valid_seed_dataset_payload()
    del payload["content_hash"]
    with pytest.raises(ValidationError):
        SeedDataset.model_validate(payload)


def test_seed_dataset_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SeedDataset.model_validate(_valid_seed_dataset_payload(row_version=2))


def test_generated_sql_contains_both_new_tables_with_rls() -> None:
    sql = GENERATED_SQL.read_text(encoding="utf-8")
    for table in ("seed_datasets", "product_environments"):
        assert f"CREATE TABLE {table} (" in sql, table
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;" in sql, table
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;" in sql, table
        assert f"{table}_tenant_isolation" in sql, table


def test_generated_sql_marks_scope_columns_not_null() -> None:
    sql = GENERATED_SQL.read_text(encoding="utf-8")
    for table in ("seed_datasets", "product_environments"):
        header = f"CREATE TABLE {table} ("
        start = sql.index(header)
        end = sql.index(";", start)
        body = sql[start:end]
        assert "tenant_id uuid NOT NULL" in body, table
        assert "project_id uuid NOT NULL" in body, table
