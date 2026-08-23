"""Chapter 19.1 schema/contract tests for the DomainInvariant and
InvariantEvaluation objects (Chapter 11.5).

Pins: valid minimal rows, unknown-field rejection, enum discipline on
`predicate.kind`/`product_env_class`/definition `status`/evaluation
`status`, versioned content-hashed definitions, the evaluation row's
append-only identity fields, generated-code drift (the generated SQL
bundle must contain both new tables with RLS), and Chapter 3.2 RLS
emission plus non-null scope columns for both new tables.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from engine.contracts.domain_invariant import DomainInvariant
from engine.contracts.invariant_evaluation import InvariantEvaluation
from engine.core.ids import uuid7

ROOT = Path(__file__).resolve().parents[2]
GENERATED_SQL = ROOT / "schemas" / "sql" / "0001_stage1.sql"


def _now() -> datetime:
    return datetime.now(UTC)


def _valid_invariant_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "invariant_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "mission_id": None,
        "name": "accounting_posting_balance",
        "description": (
            "Every accepted requirement links to a charter; posting lines "
            "balance per journal entry"
        ),
        "predicate": {
            "kind": "tuple_condition",
            "table_ref": "public.journal_lines",
            "condition": "sum(amount) = 0",
            "where": ["entry_id IS NOT NULL"],
        },
        "financial_state": True,
        "required_fixture_class": "erp-postings",
        "product_env_class": "integration",
        "definition_version": "a" * 64,
        "status": "ACTIVE",
        "created_by": "principal-1",
        "created_at": _now(),
        "updated_at": _now(),
    }
    payload.update(overrides)
    return payload


def _valid_evaluation_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "evaluation_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "mission_id": None,
        "invariant_id": uuid7(),
        "definition_version": "a" * 64,
        "product_env_id": uuid7(),
        "datastore_ref": "postgres://throwaway/db",
        "sequence": 1,
        "status": "PASSED",
        "violations": [],
        "rows_checked": 42,
        "financial_state": True,
        "repair_task_ref": None,
        "seed_dataset_id": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    payload.update(overrides)
    return payload


def test_domain_invariant_valid_with_required_fields() -> None:
    record = DomainInvariant.model_validate(_valid_invariant_payload())
    assert record.status == "ACTIVE"
    assert record.financial_state is True
    assert len(record.definition_version) == 64


def test_domain_invariant_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        DomainInvariant.model_validate(
            _valid_invariant_payload(sql="DROP TABLE tenants")
        )


def test_domain_invariant_rejects_unknown_predicate_kind() -> None:
    payload = _valid_invariant_payload()
    payload["predicate"] = {"kind": "raw_sql", "table_ref": "t"}
    with pytest.raises(ValidationError):
        DomainInvariant.model_validate(payload)


def test_domain_invariant_rejects_unknown_product_env_class() -> None:
    with pytest.raises(ValidationError):
        DomainInvariant.model_validate(
            _valid_invariant_payload(product_env_class="sandbox")
        )


def test_domain_invariant_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        DomainInvariant.model_validate(_valid_invariant_payload(status="DELETED"))


def test_domain_invariant_definition_version_is_required() -> None:
    # The generator emits no length constraints (see content_hash on
    # ProductConstitutionVersion); the 64-hex discipline is enforced where
    # versions are minted -- engine.invariants.hashing.definition_version_hash,
    # pinned by the pure unit suite.
    payload = _valid_invariant_payload()
    del payload["definition_version"]
    with pytest.raises(ValidationError):
        DomainInvariant.model_validate(payload)


def test_invariant_evaluation_valid_with_required_fields() -> None:
    record = InvariantEvaluation.model_validate(_valid_evaluation_payload())
    assert record.status == "PASSED"
    assert record.violations == []
    assert record.repair_task_ref is None


def test_invariant_evaluation_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        InvariantEvaluation.model_validate(_valid_evaluation_payload(extra=True))


def test_invariant_evaluation_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        InvariantEvaluation.model_validate(_valid_evaluation_payload(status="REPAIRED"))


def test_generated_sql_contains_both_new_tables_with_rls() -> None:
    sql = GENERATED_SQL.read_text(encoding="utf-8")
    for table in ("domain_invariants", "invariant_evaluations"):
        assert f"CREATE TABLE {table} (" in sql, table
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;" in sql, table
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;" in sql, table
        assert f"{table}_tenant_isolation" in sql, table


def test_generated_sql_marks_scope_columns_not_null() -> None:
    sql = GENERATED_SQL.read_text(encoding="utf-8")
    for table in ("domain_invariants", "invariant_evaluations"):
        header = f"CREATE TABLE {table} ("
        start = sql.index(header)
        end = sql.index(";", start)
        body = sql[start:end]
        assert "tenant_id uuid NOT NULL" in body, table
        assert "project_id uuid NOT NULL" in body, table


def test_generated_sql_pins_evaluation_append_only_identity() -> None:
    sql = GENERATED_SQL.read_text(encoding="utf-8")
    header = "CREATE TABLE invariant_evaluations ("
    start = sql.index(header)
    body = sql[start : sql.index(";", start)]
    assert (
        "UNIQUE (tenant_id, project_id, invariant_id, product_env_id, sequence)" in body
    )
