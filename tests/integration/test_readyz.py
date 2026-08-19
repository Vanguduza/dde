"""Readiness and migration tests against live PostgreSQL and Redis."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from engine.gateway.app import create_app
from engine.gateway.settings import get_settings

STAGE1_TABLES = {
    "tenants",
    "projects",
    "principals",
    "principal_grants",
    "requirements",
    "edrs",
    "product_constitution_versions",
    "missions",
    "task_graphs",
    "task_graph_edges",
    "tasks",
    "context_packages",
    "route_decisions",
    "execution_plans",
    "execution_environments",
    "workspaces",
    "task_attempts",
    "worker_runs",
    "worker_events",
    "artifacts",
    "verification_runs",
    "evidence",
    "events",
    "outbox",
    "command_idempotency",
    "audit_events",
}


def test_readyz_requires_database_redis_and_head_migrations() -> None:
    get_settings.cache_clear()
    client = TestClient(create_app())
    response = client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["database"] is True
    assert body["redis"] is True
    assert body["migrations"] == "head"


@pytest.mark.asyncio
async def test_stage1_tables_and_rls_exist() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as connection:
        table_rows = await connection.execute(
            text(
                "SELECT c.relname FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')"
            )
        )
        tables = {row[0] for row in table_rows.all()}
        assert STAGE1_TABLES <= tables
        rls_rows = await connection.execute(
            text(
                "SELECT c.relname FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') "
                "AND c.relrowsecurity AND c.relforcerowsecurity"
            )
        )
        secured = {row[0] for row in rls_rows.all()}
        assert STAGE1_TABLES <= secured
        policy_rows = await connection.execute(
            text(
                "SELECT tablename FROM pg_policies "
                "WHERE schemaname = 'public' "
                "AND policyname LIKE '%\\_tenant_isolation' ESCAPE '\\'"
            )
        )
        policies = {row[0] for row in policy_rows.all()}
        assert STAGE1_TABLES <= policies
    await engine.dispose()
