"""Chapter 19.1 schema/contract tests for Chapter 13.8 Donor Lab objects.

Pins: DonorArtifact six-value source_class + rank-9 authority, FeatureDNA
stub status, unknown-field rejection, and generated SQL + RLS for both
tables (DDE-046).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from engine.contracts.donor_artifact import DonorArtifact
from engine.contracts.feature_dna import FeatureDNA
from engine.core.ids import uuid7

ROOT = Path(__file__).resolve().parents[2]
GENERATED_SQL = ROOT / "schemas" / "sql" / "0001_stage1.sql"


def _now() -> datetime:
    return datetime.now(UTC)


def _valid_artifact_payload(**overrides: object) -> dict[str, object]:
    now = _now()
    payload: dict[str, object] = {
        "donor_artifact_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "mission_id": None,
        "source_uri": "file:///fixtures/donor/readme.md",
        "content_hash": "abc123",
        "source_class": "UNKNOWN",
        "authority_rank": 9,
        "media_kind": "readme",
        "status": "INGESTED",
        "provenance": {"entry": "manual_pin"},
        "feature_dna_id": None,
        "injection_findings": [],
        "created_at": now,
        "updated_at": now,
    }
    payload.update(overrides)
    return payload


def _valid_feature_dna_payload(**overrides: object) -> dict[str, object]:
    now = _now()
    payload: dict[str, object] = {
        "feature_dna_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "donor_artifact_id": uuid7(),
        "title": "Donor stub: file:///fixtures/donor/readme.md",
        "body": {"kind": "feature_dna_stub", "extraction": "stub"},
        "donor_sources": ["file:///fixtures/donor/readme.md"],
        "dna_hash": "dna-abc",
        "taint_tags": ["donor:x", "class:UNKNOWN"],
        "status": "STUB",
        "created_at": now,
        "updated_at": now,
    }
    payload.update(overrides)
    return payload


def test_donor_artifact_valid_with_required_fields() -> None:
    record = DonorArtifact.model_validate(_valid_artifact_payload())
    assert record.source_class == "UNKNOWN"
    assert record.authority_rank == 9
    assert record.media_kind == "readme"


def test_donor_artifact_rejects_unknown_source_class() -> None:
    payload = _valid_artifact_payload(source_class="FREE_FOR_ALL")
    with pytest.raises(ValidationError):
        DonorArtifact.model_validate(payload)


def test_donor_artifact_rejects_missing_content_hash() -> None:
    payload = _valid_artifact_payload()
    del payload["content_hash"]
    with pytest.raises(ValidationError):
        DonorArtifact.model_validate(payload)


def test_donor_artifact_rejects_unknown_fields() -> None:
    payload = _valid_artifact_payload(invented=True)
    with pytest.raises(ValidationError):
        DonorArtifact.model_validate(payload)


def test_feature_dna_valid_stub_status() -> None:
    record = FeatureDNA.model_validate(_valid_feature_dna_payload())
    assert record.status == "STUB"
    assert record.body["kind"] == "feature_dna_stub"


def test_feature_dna_rejects_unknown_status() -> None:
    payload = _valid_feature_dna_payload(status="DRAFT")
    with pytest.raises(ValidationError):
        FeatureDNA.model_validate(payload)


def test_feature_dna_rejects_missing_dna_hash() -> None:
    payload = _valid_feature_dna_payload()
    del payload["dna_hash"]
    with pytest.raises(ValidationError):
        FeatureDNA.model_validate(payload)


def test_feature_dna_rejects_unknown_fields() -> None:
    payload = _valid_feature_dna_payload(notes="nope")
    with pytest.raises(ValidationError):
        FeatureDNA.model_validate(payload)


def test_generated_sql_contains_donor_lab_tables_and_rls() -> None:
    sql = GENERATED_SQL.read_text(encoding="utf-8")
    for table in ("donor_artifacts", "feature_dna"):
        assert f"CREATE TABLE {table} (" in sql, table
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;" in sql, table
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;" in sql, table
        assert f"{table}_tenant_isolation" in sql, table
    assert "UNIQUE (project_id, content_hash)" in sql
    assert "UNIQUE (project_id, dna_hash)" in sql
