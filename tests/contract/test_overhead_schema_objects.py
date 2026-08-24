"""Chapter 19.1 schema/contract tests for Chapter 16.4 overhead objects.

Pins: formula component fields on ControlPlaneOverheadTask, the
WorkloadClassCostMetrics unique (tenant, project, workload_class),
unknown-field rejection, and generated SQL + RLS for both tables.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from engine.contracts.control_plane_overhead_task import ControlPlaneOverheadTask
from engine.contracts.workload_class_cost_metrics import WorkloadClassCostMetrics
from engine.core.ids import uuid7

ROOT = Path(__file__).resolve().parents[2]
GENERATED_SQL = ROOT / "schemas" / "sql" / "0001_stage1.sql"


def _now() -> datetime:
    return datetime.now(UTC)


def _valid_overhead_payload(**overrides: object) -> dict[str, object]:
    now = _now()
    payload: dict[str, object] = {
        "overhead_task_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "mission_id": uuid7(),
        "task_id": uuid7(),
        "task_attempt_id": uuid7(),
        "worker_run_id": uuid7(),
        "execution_plan_id": uuid7(),
        "context_package_id": uuid7(),
        "environment_id": uuid7(),
        "estimated_effort": "s",
        "context_assembly_tokens": 10,
        "context_critic_tokens": 2,
        "routing_tokens": 0,
        "route_critic_tokens": 0,
        "planning_tokens": 0,
        "judge_tokens": 0,
        "overhead_tokens": 12,
        "environment_provisioning_ms": 100,
        "queue_wait_seconds": 0.5,
        "overhead_seconds_before_first_worker_action_seconds": 1.5,
        "context_critic_invoked": True,
        "route_critic_invoked": False,
        "workload_class": "bulk_implementation",
        "created_at": now,
        "updated_at": now,
    }
    payload.update(overrides)
    return payload


def _valid_cost_payload(**overrides: object) -> dict[str, object]:
    now = _now()
    payload: dict[str, object] = {
        "metric_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "workload_class": "bulk_implementation",
        "verified_success_count": 3,
        "total_overhead_tokens": 30,
        "cost_tokens_per_verified_success": 10.0,
        "created_at": now,
        "updated_at": now,
    }
    payload.update(overrides)
    return payload


def test_control_plane_overhead_task_requires_formula_components() -> None:
    record = ControlPlaneOverheadTask.model_validate(_valid_overhead_payload())
    assert record.routing_tokens == 0
    assert record.route_critic_tokens == 0
    assert record.planning_tokens == 0
    assert record.judge_tokens == 0
    assert record.route_critic_invoked is False
    assert record.workload_class == "bulk_implementation"


def test_control_plane_overhead_task_rejects_missing_routing_tokens() -> None:
    payload = _valid_overhead_payload()
    del payload["routing_tokens"]
    with pytest.raises(ValidationError):
        ControlPlaneOverheadTask.model_validate(payload)


def test_control_plane_overhead_task_rejects_unknown_fields() -> None:
    payload = _valid_overhead_payload()
    payload["invented"] = True
    with pytest.raises(ValidationError):
        ControlPlaneOverheadTask.model_validate(payload)


def test_workload_class_cost_metrics_valid_with_required_fields() -> None:
    record = WorkloadClassCostMetrics.model_validate(_valid_cost_payload())
    assert record.verified_success_count == 3
    assert record.cost_tokens_per_verified_success == 10.0


def test_workload_class_cost_metrics_rejects_missing_workload_class() -> None:
    payload = _valid_cost_payload()
    del payload["workload_class"]
    with pytest.raises(ValidationError):
        WorkloadClassCostMetrics.model_validate(payload)


def test_workload_class_cost_metrics_rejects_unknown_fields() -> None:
    payload = _valid_cost_payload()
    payload["notes"] = "nope"
    with pytest.raises(ValidationError):
        WorkloadClassCostMetrics.model_validate(payload)


def test_generated_sql_contains_overhead_formula_columns_and_cost_table() -> None:
    sql = GENERATED_SQL.read_text(encoding="utf-8")
    assert "routing_tokens integer NOT NULL" in sql
    assert "route_critic_tokens integer NOT NULL" in sql
    assert "planning_tokens integer NOT NULL" in sql
    assert "judge_tokens integer NOT NULL" in sql
    assert "route_critic_invoked boolean NOT NULL" in sql
    assert "workload_class text NOT NULL" in sql
    for table in ("control_plane_overhead_tasks", "workload_class_cost_metrics"):
        assert f"CREATE TABLE {table} (" in sql, table
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;" in sql, table
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;" in sql, table
        assert f"{table}_tenant_isolation" in sql, table
