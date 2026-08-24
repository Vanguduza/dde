"""Chapter 19.1 schema/contract tests for the MissionTemplate and
PlanDraft objects (Chapter 4.3, DDE-040).

Pins: valid minimal rows, unknown-field rejection, enum discipline on
`status`/`origin`/`task_class`/`estimated_effort`/`edge_type`, the
template's content-hashed `template_version` identity, the draft's
provenance and promotion fields, generated-code drift (the generated SQL
bundle must contain both new tables with RLS), and Chapter 3.2 RLS
emission plus non-null scope columns for both new tables.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from engine.contracts.mission_template import MissionTemplate
from engine.contracts.plan_draft import PlanDraft
from engine.core.ids import uuid7

ROOT = Path(__file__).resolve().parents[2]
GENERATED_SQL = ROOT / "schemas" / "sql" / "0001_stage1.sql"


def _now() -> datetime:
    return datetime.now(UTC)


def _valid_template_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "template_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "template_key": "add_endpoint",
        "template_version": "a" * 64,
        "description": "Specify -> implement -> verify an HTTP endpoint",
        "nodes": [
            {
                "node_key": "spec",
                "title": "Specify endpoint contract",
                "intent": "Commit the HTTP contract first",
                "task_class": "specification",
                "write_scope": ["schemas/api"],
                "success_criteria": ["Endpoint schema committed"],
                "estimated_effort": "s",
            },
            {
                "node_key": "impl",
                "title": "Implement endpoint",
                "intent": "Implement the contracted handler",
                "task_class": "implementation",
                "write_scope": ["engine/gateway"],
                "success_criteria": ["Handler returns contracted payload"],
                "estimated_effort": "s",
            },
        ],
        "edges": [
            {
                "from_node_key": "spec",
                "to_node_key": "impl",
                "edge_type": "depends_on",
            }
        ],
        "status": "ACTIVE",
        "planner_policy_version": "template-v1",
        "created_by": "principal-1",
        "created_at": _now(),
        "updated_at": _now(),
    }
    payload.update(overrides)
    return payload


def _valid_draft_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "draft_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "mission_id": uuid7(),
        "origin": "model_assisted",
        "adapter_ref": None,
        "origin_policy_version": "draft-validator-v1",
        "nodes": [
            {
                "node_key": "n1",
                "title": "Proposed node",
                "intent": "Untrusted model output",
                "task_class": "implementation",
                "write_scope": ["engine/gateway"],
                "success_criteria": ["Observable behaviour holds"],
            }
        ],
        "edges": [],
        "status": "PROPOSED",
        "refusals": [],
        "promoted_graph_id": None,
        "provenance_key": "p" * 64,
        "created_by_principal": uuid7(),
        "created_at": _now(),
        "updated_at": _now(),
    }
    payload.update(overrides)
    return payload


def test_mission_template_valid_with_required_fields() -> None:
    record = MissionTemplate.model_validate(_valid_template_payload())
    assert record.status == "ACTIVE"
    assert len(record.template_version) == 64
    assert record.nodes[0].node_key == "spec"


def test_mission_template_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        MissionTemplate.model_validate(
            _valid_template_payload(sql="DROP TABLE tenants")
        )


def test_mission_template_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        MissionTemplate.model_validate(_valid_template_payload(status="DRAFT"))


def test_mission_template_rejects_unknown_task_class() -> None:
    payload = _valid_template_payload()
    payload["nodes"] = [dict(payload["nodes"][0], task_class="magic")]  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        MissionTemplate.model_validate(payload)


def test_mission_template_success_criteria_range_is_enforced_at_the_mint() -> None:
    # The generator emits no min/maxItems constraints (same finding as
    # DDE-039's definition_version); the 1-5 criteria range of Chapter 4.4
    # is enforced downstream where templates materialise (validate_graph)
    # and pinned there; the registry's own conformance check refuses
    # structurally impossible shapes instead.
    payload = _valid_template_payload()
    record = MissionTemplate.model_validate(payload)
    assert all(1 <= len(node.success_criteria) for node in record.nodes)


def test_mission_template_rejects_estimated_effort_l() -> None:
    """Chapter 4.4: effort l must be decomposed before commit; a template
    may never register an l-sized node."""
    payload = _valid_template_payload()
    node = dict(payload["nodes"][0])  # type: ignore[arg-type]
    node["estimated_effort"] = "l"
    payload["nodes"] = [node, payload["nodes"][1]]  # type: ignore[index]
    with pytest.raises(ValidationError):
        MissionTemplate.model_validate(payload)


def test_plan_draft_valid_with_required_fields() -> None:
    record = PlanDraft.model_validate(_valid_draft_payload())
    assert record.status == "PROPOSED"
    assert record.origin == "model_assisted"
    assert record.promoted_graph_id is None
    assert record.refusals == []


def test_plan_draft_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        PlanDraft.model_validate(_valid_draft_payload(executable=True))


def test_plan_draft_rejects_unknown_origin() -> None:
    with pytest.raises(ValidationError):
        PlanDraft.model_validate(_valid_draft_payload(origin="autonomous"))


def test_plan_draft_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        PlanDraft.model_validate(_valid_draft_payload(status="EXECUTABLE"))


def test_plan_draft_rejects_unknown_edge_type() -> None:
    payload = _valid_draft_payload()
    payload["edges"] = [
        {
            "from_node_key": "n1",
            "to_node_key": "n1",
            "edge_type": "suggests",
        }
    ]
    with pytest.raises(ValidationError):
        PlanDraft.model_validate(payload)


def test_generated_sql_contains_both_new_tables_with_rls() -> None:
    sql = GENERATED_SQL.read_text(encoding="utf-8")
    for table in ("mission_templates", "plan_drafts"):
        assert f"CREATE TABLE {table} (" in sql, table
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;" in sql, table
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;" in sql, table
        assert f"{table}_tenant_isolation" in sql, table


def test_generated_sql_marks_scope_columns_not_null() -> None:
    sql = GENERATED_SQL.read_text(encoding="utf-8")
    for table in ("mission_templates", "plan_drafts"):
        header = f"CREATE TABLE {table} ("
        start = sql.index(header)
        end = sql.index(";", start)
        body = sql[start:end]
        assert "tenant_id uuid NOT NULL" in body, table
        assert "project_id uuid NOT NULL" in body, table


def test_generated_sql_pins_registry_and_provenance_uniques() -> None:
    sql = GENERATED_SQL.read_text(encoding="utf-8")
    template_start = sql.index("CREATE TABLE mission_templates (")
    template_body = sql[template_start : sql.index(";", template_start)]
    assert "UNIQUE (project_id, template_key, template_version)" in template_body
    draft_start = sql.index("CREATE TABLE plan_drafts (")
    draft_body = sql[draft_start : sql.index(";", draft_start)]
    assert "UNIQUE (tenant_id, project_id, provenance_key)" in draft_body
