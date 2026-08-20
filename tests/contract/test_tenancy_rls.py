"""Contract tests for Chapter 3.2 tenancy columns and Chapter 13.9 RLS.

These tests read `schemas/objects` and the generated `0001_stage1.sql`.
They must fail if tenancy columns are optional on a table Chapter 3.2
requires, or if generated RLS omits FORCE / the GUC predicates.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OBJECTS = ROOT / "schemas" / "objects"
GENERATED_SQL = ROOT / "schemas" / "sql" / "0001_stage1.sql"

# Chapter 3.2 names three global registries. Only `capabilities` exists in
# the Stage 1/2 table set; `worker_profiles` and `policies` are deferred
# until those objects are chartered into schema.
GLOBAL_REGISTRIES = frozenset({"capabilities"})
DEFERRED_GLOBAL_REGISTRIES = frozenset({"worker_profiles", "policies"})

# Tenant-wide hash chain (Chapter 3.7): project_id is correlation metadata,
# not an RLS axis. See schemas/objects/audit_event.json.
TENANT_ONLY_WITH_OPTIONAL_PROJECT = frozenset({"audit_events"})


def _stored_objects() -> list[dict[str, Any]]:
    stored: list[dict[str, Any]] = []
    for path in sorted(OBJECTS.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if "x-dde-storage" in payload:
            stored.append(payload)
    stored.sort(key=lambda item: int(item["x-dde-storage"]["order"]))
    return stored


def _policy_sql(sql: str, table: str) -> str:
    pattern = (
        rf"CREATE POLICY {re.escape(table)}_tenant_isolation "
        rf"ON {re.escape(table)} (.+);"
    )
    match = re.search(pattern, sql)
    assert match is not None, f"missing RLS policy for {table}"
    return match.group(1)


def test_deferred_global_registries_are_not_silently_invented() -> None:
    tables = {item["x-dde-storage"]["table"] for item in _stored_objects()}
    assert DEFERRED_GLOBAL_REGISTRIES.isdisjoint(tables)


def test_every_stored_table_except_global_registries_requires_tenant_id() -> None:
    for schema in _stored_objects():
        storage = schema["x-dde-storage"]
        table = storage["table"]
        required = set(schema.get("required") or [])
        if table in GLOBAL_REGISTRIES:
            assert "tenant_id" not in required
            assert "tenant_id" not in schema["properties"]
            assert "owner_tenant_id" in schema["properties"]
            assert "visibility" in required
            continue
        assert storage.get("tenant_scoped") is True, table
        assert "tenant_id" in required, table
        tenant_schema = schema["properties"]["tenant_id"]
        assert tenant_schema.get("type") == "string"
        assert tenant_schema.get("format") == "uuid"


def test_project_scoped_tables_require_non_null_project_id() -> None:
    for schema in _stored_objects():
        storage = schema["x-dde-storage"]
        table = storage["table"]
        if table in GLOBAL_REGISTRIES:
            continue
        required = set(schema.get("required") or [])
        if table in TENANT_ONLY_WITH_OPTIONAL_PROJECT:
            assert storage.get("project_scoped") is False, table
            assert "project_id" in schema["properties"]
            assert "project_id" not in required
            continue
        if not storage.get("project_scoped"):
            continue
        assert "project_id" in required, table
        project_schema = schema["properties"]["project_id"]
        assert project_schema.get("type") == "string", table
        assert project_schema.get("format") == "uuid", table


def test_generated_sql_enables_and_forces_rls_on_every_scoped_table() -> None:
    sql = GENERATED_SQL.read_text(encoding="utf-8")
    for schema in _stored_objects():
        storage = schema["x-dde-storage"]
        table = storage["table"]
        if not storage.get("tenant_scoped") and not storage.get("rls_predicate"):
            continue
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;" in sql, table
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;" in sql, table
        policy = _policy_sql(sql, table)
        assert "USING (" in policy, table
        assert "WITH CHECK (" in policy, table
        if storage.get("rls_predicate"):
            assert storage["rls_predicate"] in policy
            continue
        assert "current_setting('dde.tenant_id', true)" in policy, table
        if storage.get("project_scoped"):
            assert "current_setting('dde.project_id', true)" in policy, table
        else:
            assert "current_setting('dde.project_id', true)" not in policy, table


def test_capabilities_rls_predicate_is_visibility_or_owner_tenant() -> None:
    sql = GENERATED_SQL.read_text(encoding="utf-8")
    policy = _policy_sql(sql, "capabilities")
    assert "visibility = 'global'" in policy
    assert (
        "owner_tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid)"
        in policy
    )
    assert "USING (tenant_id =" not in policy


def test_generated_create_table_marks_tenant_id_not_null() -> None:
    sql = GENERATED_SQL.read_text(encoding="utf-8")
    for schema in _stored_objects():
        table = schema["x-dde-storage"]["table"]
        if table in GLOBAL_REGISTRIES:
            continue
        header = f"CREATE TABLE {table} ("
        start = sql.index(header)
        end = sql.index(";", start)
        body = sql[start:end]
        assert "tenant_id uuid NOT NULL" in body, table
