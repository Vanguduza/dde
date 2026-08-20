"""Chapter 13.9 / 3.2 RLS enforcement suite.

Proves fail-closed isolation through `dde_rls_probe` (NOSUPERUSER
NOBYPASSRLS). The local `dde` owner role is a superuser and always
bypasses RLS, so these tests never treat a superuser SELECT as evidence
that a policy holds.

What this suite claims. Database RLS (the first of Chapter 13.9's four
isolation layers): missing GUC yields no tenant-scoped rows; a wrong
tenant GUC cannot read or write another tenant's rows; a wrong project
GUC cannot read another project's rows on project-scoped tables; INSERT
WITH CHECK rejects a row whose tenant_id does not match the GUC.

What this suite does not claim. Principal-derived identity, object-storage
key prefixes, project-scoped Git credentials, or telemetry-scoped
dashboards (the rest of Chapter 13.9). Those are deferred -- see the
mission report, not a passing test.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.missions.service import MissionService
from engine.truth.db import open_unit_of_work
from engine.truth.service import TruthService
from tests.support.db import (
    RLS_PROBE_ROLE,
    TenantFixture,
    ensure_rls_probe_role,
    load_stored_object_schemas,
    new_engine,
    open_rls_probe,
    seed_tenant,
)


def _rls_tables() -> list[tuple[str, bool, bool]]:
    """(table, uses_default_tenant_predicate, project_scoped)."""
    rows: list[tuple[str, bool, bool]] = []
    for schema in load_stored_object_schemas():
        storage = schema["x-dde-storage"]
        table = storage["table"]
        if not storage.get("tenant_scoped") and not storage.get("rls_predicate"):
            continue
        default = storage.get("rls_predicate") is None
        rows.append((table, default, bool(storage.get("project_scoped"))))
    return rows


async def _seed_second_project(engine, tenant_id: UUID) -> UUID:
    project_id = uuid7()
    now = datetime.now(UTC)
    async with open_unit_of_work(
        engine, tenant_id=tenant_id, project_id=project_id
    ) as uow:
        await uow.connection.execute(
            text(
                "INSERT INTO projects "
                "(project_id, tenant_id, slug, created_at, updated_at) "
                "VALUES (:project_id, :tenant_id, :slug, :now, :now)"
            ),
            {
                "project_id": project_id,
                "tenant_id": tenant_id,
                "slug": f"project-{project_id.hex}",
                "now": now,
            },
        )
        await uow.commit()
    return project_id


async def _draft_requirement(engine, fixture: TenantFixture, slug: str) -> UUID:
    service = TruthService(engine)
    record = await service.draft_requirement(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        slug=slug,
        statement="RLS enforcement fixture",
        constraints=[],
        acceptance_conditions=["isolated"],
    )
    return record.requirement_id


@pytest.mark.asyncio
async def test_rls_probe_role_cannot_bypass_rls() -> None:
    engine = new_engine()
    try:
        probe_url = await ensure_rls_probe_role(engine)
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT rolsuper, rolbypassrls FROM pg_roles "
                        "WHERE rolname = :role"
                    ),
                    {"role": RLS_PROBE_ROLE},
                )
            ).one()
        assert row[0] is False
        assert row[1] is False
        assert "dde_rls_probe" in probe_url
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_every_stored_table_has_force_rls_and_guc_policy() -> None:
    engine = new_engine()
    try:
        async with engine.connect() as connection:
            tables = {table for table, _, _ in _rls_tables()}
            rel = await connection.execute(
                text(
                    "SELECT c.relname FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') "
                    "AND c.relrowsecurity AND c.relforcerowsecurity"
                )
            )
            forced = {row[0] for row in rel.all()}
            assert tables <= forced

            policies = await connection.execute(
                text(
                    "SELECT tablename, qual, with_check FROM pg_policies "
                    "WHERE schemaname = 'public' "
                    "AND policyname LIKE '%\\_tenant_isolation' ESCAPE '\\'"
                )
            )
            by_table = {row[0]: (row[1], row[2]) for row in policies.all()}
            for table, default_pred, project_scoped in _rls_tables():
                assert table in by_table, table
                using, check = by_table[table]
                assert using
                assert check
                if not default_pred:
                    continue
                assert "dde.tenant_id" in using, table
                assert "dde.tenant_id" in check, table
                if project_scoped:
                    assert "dde.project_id" in using, table
                    assert "dde.project_id" in check, table
                else:
                    assert "dde.project_id" not in using, table
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_missing_tenant_guc_yields_no_rows_on_every_tenant_table() -> None:
    """Chapter 3.2: unset GUC yields no rows. Capabilities with
    visibility=global remain visible -- that predicate is the Chapter 3.2
    global-registry exception, not a hole in tenant isolation.

    Empty tables cannot prove fail-closed; this seeds identity + a
    requirement + a mission (which also writes events/outbox) and asserts
    the probe sees none of those rows.
    """
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        await _draft_requirement(
            engine, fixture, slug=f"REQ-RLS-NOGUC-{uuid7().hex[:12]}"
        )
        await MissionService(engine, EventService(engine)).create_mission(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            slug=f"MISSION-RLS-NOGUC-{uuid7().hex[:12]}",
            title="Missing GUC",
            intent="Hidden without a tenant setting",
            success_definition="Probe without GUC sees zero rows",
            scope=["engine"],
            requirement_refs=[],
            autonomy_ceiling=1,
        )
        occupied: set[str] = set()
        async with engine.connect() as connection:
            for table, default_pred, _project_scoped in _rls_tables():
                if table == "capabilities" or not default_pred:
                    continue
                count = await connection.execute(
                    text(f"SELECT count(*) FROM {table}")  # noqa: S608
                )
                if count.scalar_one() > 0:
                    occupied.add(table)
        assert occupied >= {
            "tenants",
            "projects",
            "principals",
            "requirements",
            "missions",
        }
        probe_url = await ensure_rls_probe_role(engine)
        probe_engine = create_async_engine(probe_url)
        try:
            async with open_rls_probe(probe_engine) as connection:
                for table in occupied:
                    count = await connection.execute(
                        text(f"SELECT count(*) FROM {table}")  # noqa: S608
                    )
                    assert count.scalar_one() == 0, table
                hidden_caps = await connection.execute(
                    text(
                        "SELECT count(*) FROM capabilities WHERE visibility = 'tenant'"
                    )
                )
                assert hidden_caps.scalar_one() == 0
        finally:
            await probe_engine.dispose()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_wrong_tenant_guc_cannot_read_or_write_requirement() -> None:
    engine = new_engine()
    try:
        owner = await seed_tenant(engine)
        stranger = await seed_tenant(engine)
        requirement_id = await _draft_requirement(
            engine, owner, slug=f"REQ-RLS-XTENANT-{uuid7().hex[:12]}"
        )
        probe_url = await ensure_rls_probe_role(engine)
        probe_engine = create_async_engine(probe_url)
        try:
            async with open_rls_probe(
                probe_engine,
                tenant_id=stranger.tenant_id,
                project_id=stranger.project_id,
            ) as connection:
                visible = await connection.execute(
                    text("SELECT 1 FROM requirements WHERE requirement_id = :id"),
                    {"id": requirement_id},
                )
                assert visible.first() is None
                updated = await connection.execute(
                    text(
                        "UPDATE requirements SET statement = 'pwned' "
                        "WHERE requirement_id = :id"
                    ),
                    {"id": requirement_id},
                )
                assert updated.rowcount == 0
                deleted = await connection.execute(
                    text("DELETE FROM requirements WHERE requirement_id = :id"),
                    {"id": requirement_id},
                )
                assert deleted.rowcount == 0

            now = datetime.now(UTC)
            async with open_rls_probe(
                probe_engine,
                tenant_id=stranger.tenant_id,
                project_id=stranger.project_id,
            ) as connection:
                with pytest.raises(DBAPIError, match="row-level security"):
                    await connection.execute(
                        text(
                            "INSERT INTO requirements ("
                            "requirement_id, tenant_id, project_id, slug, "
                            "statement, constraints, acceptance_conditions, "
                            "status, created_at, updated_at"
                            ") VALUES ("
                            ":id, :tenant_id, :project_id, :slug, "
                            ":statement, '[]'::jsonb, '[]'::jsonb, "
                            "'draft', :now, :now)"
                        ),
                        {
                            "id": uuid7(),
                            "tenant_id": owner.tenant_id,
                            "project_id": owner.project_id,
                            "slug": f"REQ-RLS-INSERT-{uuid7().hex[:12]}",
                            "statement": "cross-tenant insert",
                            "now": now,
                        },
                    )
        finally:
            await probe_engine.dispose()

        async with open_unit_of_work(
            engine, tenant_id=owner.tenant_id, project_id=owner.project_id
        ) as uow:
            still = await uow.connection.execute(
                text("SELECT statement FROM requirements WHERE requirement_id = :id"),
                {"id": requirement_id},
            )
            row = still.one()
            assert row[0] == "RLS enforcement fixture"
            await uow.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_wrong_project_guc_cannot_read_same_tenant_requirement() -> None:
    engine = new_engine()
    try:
        owner = await seed_tenant(engine)
        other_project_id = await _seed_second_project(engine, owner.tenant_id)
        requirement_id = await _draft_requirement(
            engine, owner, slug=f"REQ-RLS-XPROJECT-{uuid7().hex[:12]}"
        )
        probe_url = await ensure_rls_probe_role(engine)
        probe_engine = create_async_engine(probe_url)
        try:
            async with open_rls_probe(
                probe_engine,
                tenant_id=owner.tenant_id,
                project_id=other_project_id,
            ) as connection:
                hidden = await connection.execute(
                    text("SELECT 1 FROM requirements WHERE requirement_id = :id"),
                    {"id": requirement_id},
                )
                assert hidden.first() is None
            async with open_rls_probe(
                probe_engine,
                tenant_id=owner.tenant_id,
                project_id=owner.project_id,
            ) as connection:
                visible = await connection.execute(
                    text("SELECT 1 FROM requirements WHERE requirement_id = :id"),
                    {"id": requirement_id},
                )
                assert visible.first() is not None
        finally:
            await probe_engine.dispose()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_wrong_tenant_guc_cannot_read_mission() -> None:
    engine = new_engine()
    try:
        owner = await seed_tenant(engine)
        stranger = await seed_tenant(engine)
        created = await MissionService(engine, EventService(engine)).create_mission(
            tenant_id=owner.tenant_id,
            project_id=owner.project_id,
            slug=f"MISSION-RLS-XTENANT-{uuid7().hex[:12]}",
            title="Cross-tenant RLS",
            intent="Hidden from the other tenant",
            success_definition="Probe with stranger GUC sees nothing",
            scope=["engine"],
            requirement_refs=[],
            autonomy_ceiling=1,
        )
        probe_url = await ensure_rls_probe_role(engine)
        probe_engine = create_async_engine(probe_url)
        try:
            async with open_rls_probe(
                probe_engine,
                tenant_id=stranger.tenant_id,
                project_id=stranger.project_id,
            ) as connection:
                hidden = await connection.execute(
                    text("SELECT 1 FROM missions WHERE mission_id = :id"),
                    {"id": created.mission_id},
                )
                assert hidden.first() is None
        finally:
            await probe_engine.dispose()
    finally:
        await engine.dispose()
