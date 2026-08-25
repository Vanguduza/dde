"""Contract tests for Chapter 13.9 tenancy authority (DDE-051).

Chapter 3.2/13.9 MUSTs this file pins, all of which FAILED before DDE-051:

1. The scope chain `Principal -> Organization/Tenant -> Project -> Mission
   -> Task -> runtime bindings` is expressed in schema: an Organization row
   sits above Tenant, and Tenant carries a required organization_id.
2. Principals gain ORGANIZATION-scoped grants (Chapter 14.2 ABAC context:
   "tenant" as authorization constraint) -- principal_grants.scope_type
   admits ORGANIZATION and the generated SQL declares it.
3. Scope-binding foreign keys: every FK that crosses a scope boundary is
   composite, so a row can never reference another scope's parent (a lone
   mission_id FK lets tenant B reference tenant A's mission; Chapter 13.9's
   "rejects cross-scope references even when an artifact id is otherwise
   valid").
4. Generated 0001_stage1.sql carries the organizations table with FORCE RLS
   and the fail-closed GUC policy shape.

These are static/schema tests: the live fail-closed behaviour suite is
tests/unit/test_multi_tenant_isolation.py.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OBJECTS = ROOT / "schemas" / "objects"
GENERATED_SQL = ROOT / "schemas" / "sql" / "0001_stage1.sql"


def _load(name: str) -> dict[str, Any]:
    return json.loads((OBJECTS / name).read_text(encoding="utf-8"))


def _policy_sql(sql: str, table: str) -> str:
    pattern = (
        rf"CREATE POLICY {re.escape(table)}_tenant_isolation "
        rf"ON {re.escape(table)} (.+);"
    )
    match = re.search(pattern, sql)
    assert match is not None, f"missing RLS policy for {table}"
    return match.group(1)


def test_organization_object_exists_above_tenant() -> None:
    schema = _load("organization.json")
    storage = schema["x-dde-storage"]
    assert storage["table"] == "organizations"
    assert storage.get("rls_predicate") == (
        "organization_id = CAST("
        "current_setting('dde.organization_id', true) AS uuid)"
    )
    assert storage.get("tenant_scoped") is False
    required = set(schema.get("required") or [])
    assert {"organization_id", "slug", "created_at", "updated_at"} <= required


def test_tenant_gains_required_organization_id() -> None:
    schema = _load("tenant.json")
    required = set(schema.get("required") or [])
    assert "organization_id" in required, "Ch.13.9: Organization above Tenant"
    fk = {
        item["name"]: item
        for item in schema["x-dde-storage"].get("foreign_keys") or []
    }
    org_fk = fk["tenants_organization_id_fkey"]
    assert org_fk["columns"] == ["organization_id"]
    assert org_fk["ref_table"] == "organizations"


def test_principal_grant_admits_organization_scope() -> None:
    schema = _load("principal_grant.json")
    scope_type = schema["properties"]["scope_type"]
    values = set(scope_type["enum"])
    assert {"ORGANIZATION", "PROJECT"} <= values
    grant_scope = schema["properties"]["grant_scope"]
    values = set(grant_scope["enum"])
    assert {"ORGANIZATION", "TENANT", "PROJECT"} <= values


def test_artifact_mission_fk_is_composite_scope_binding() -> None:
    schema = _load("artifact.json")
    names = {
        item["name"]: item
        for item in schema["x-dde-storage"].get("foreign_keys") or []
    }
    fk = names["artifacts_mission_scope_fkey"]
    assert fk["columns"] == ["mission_id", "project_id", "tenant_id"]
    assert fk["ref_table"] == "missions"
    assert fk["ref_columns"] == ["mission_id", "project_id", "tenant_id"]
    assert "artifacts_mission_id_fkey" not in names


def test_worker_run_attempt_fk_is_composite_scope_binding() -> None:
    """A WorkerRun must not be attachable to another scope's attempt even
    when both UUIDs are individually valid (adversarial self-check: could a
    new WorkerRun bypass isolation? This FK is the database-level answer)."""
    worker = _load("worker_run.json")
    task = _load("task_attempt.json")
    wk = {
        item["name"]: item
        for item in worker["x-dde-storage"].get("foreign_keys") or []
    }
    tk = {
        item["name"]: item
        for item in task["x-dde-storage"].get("foreign_keys") or []
    }
    run_fk = wk["worker_runs_task_attempt_scope_fkey"]
    assert run_fk["ref_table"] == "task_attempts"
    assert run_fk["columns"][1:] == ["project_id", "tenant_id"]
    attempt_fk = tk["task_attempts_mission_scope_fkey"]
    assert attempt_fk["ref_table"] == "missions"
    assert attempt_fk["columns"][0] == "mission_id"


def test_generated_sql_has_organizations_rls_and_grant_check_constraint() -> None:
    sql = GENERATED_SQL.read_text(encoding="utf-8")
    header = "CREATE TABLE organizations (\n"
    start = sql.index(header)
    end = sql.index(";", start)
    body = sql[start:end]
    assert "organization_id uuid NOT NULL" in body
    assert "ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;" in sql
    assert "ALTER TABLE organizations FORCE ROW LEVEL SECURITY;" in sql
    policy = _policy_sql(sql, "organizations")
    assert "dde.organization_id" in policy

    # Grant scope CHECK constraints exist on the generated table.
    grants_start = sql.index("CREATE TABLE principal_grants (\n")
    grants_body = sql[grants_start : sql.index(");", grants_start)]
    assert "scope_type text NOT NULL DEFAULT 'PROJECT'" in grants_body
    assert "CHECK (scope_type IN ('ORGANIZATION', 'PROJECT'))" in grants_body
    assert "CHECK (grant_scope IN ('ORGANIZATION', 'TENANT', 'PROJECT'))" in grants_body

    # Tenants.organisation link column exists and is NOT NULL.
    tenants_start = sql.index("CREATE TABLE tenants (\n")
    tenants_body = sql[tenants_start : sql.index(");", tenants_start)]
    assert "organization_id uuid NOT NULL" in tenants_body


def test_generated_sql_drops_single_column_scope_fks() -> None:
    sql = GENERATED_SQL.read_text(encoding="utf-8")
    assert "ADD CONSTRAINT artifacts_mission_id_fkey" not in sql
    assert "ADD CONSTRAINT worker_runs_task_attempt_id_fkey" not in sql
    assert "ADD CONSTRAINT task_attempts_mission_id_fkey" not in sql
