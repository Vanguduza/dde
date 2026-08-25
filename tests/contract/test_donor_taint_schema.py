"""Chapter 19.1 schema tests for DDE-047 donor_taint + FeatureDNA taint_tags."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from engine.contracts.donor_taint import DonorTaint
from engine.contracts.feature_dna import FeatureDNA
from engine.core.ids import uuid7

ROOT = Path(__file__).resolve().parents[2]
GENERATED_SQL = ROOT / "schemas" / "sql" / "0001_stage1.sql"


def _now() -> datetime:
    return datetime.now(UTC)


def _valid_taint(**overrides: object) -> dict[str, object]:
    now = _now()
    payload: dict[str, object] = {
        "donor_taint_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "donor_artifact_id": uuid7(),
        "subject_kind": "feature_dna",
        "subject_id": uuid7(),
        "source_class": "SOURCE_REFERENCE_ONLY",
        "licence_class": "UNKNOWN",
        "taint_tags": ["donor:abc", "class:SOURCE_REFERENCE_ONLY"],
        "source_uri": "file:///fixtures/donor/readme.md",
        "signed_reuse_decision_id": None,
        "created_at": now,
        "updated_at": now,
    }
    payload.update(overrides)
    return payload


def test_donor_taint_valid_with_required_fields() -> None:
    record = DonorTaint.model_validate(_valid_taint())
    assert record.subject_kind == "feature_dna"
    assert record.source_class == "SOURCE_REFERENCE_ONLY"
    assert "donor:abc" in record.taint_tags


def test_donor_taint_rejects_unknown_subject_kind() -> None:
    with pytest.raises(ValidationError):
        DonorTaint.model_validate(_valid_taint(subject_kind="prompt"))


def test_donor_taint_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        DonorTaint.model_validate(_valid_taint(invented=True))


def test_feature_dna_requires_taint_tags() -> None:
    now = _now()
    with pytest.raises(ValidationError):
        FeatureDNA.model_validate(
            {
                "feature_dna_id": uuid7(),
                "tenant_id": uuid7(),
                "project_id": uuid7(),
                "donor_artifact_id": uuid7(),
                "title": "x",
                "body": {},
                "donor_sources": ["u"],
                "dna_hash": "h",
                "status": "STUB",
                "created_at": now,
                "updated_at": now,
            }
        )


def test_generated_sql_contains_donor_taints_and_rls() -> None:
    sql = GENERATED_SQL.read_text(encoding="utf-8")
    assert "CREATE TABLE donor_taints (" in sql
    assert "ALTER TABLE donor_taints ENABLE ROW LEVEL SECURITY;" in sql
    assert "donor_taints_tenant_isolation" in sql
    assert "taint_tags jsonb NOT NULL" in sql
    assert "UNIQUE (project_id, subject_kind, subject_id, donor_artifact_id)" in sql
