"""EDR-0018 neutral Source Intelligence PostgreSQL/RLS certification."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from engine.core.ids import uuid7
from engine.source.service import SourceService
from engine.truth.db import open_unit_of_work
from tests.support.db import ensure_rls_probe_role, new_engine, open_rls_probe, seed_tenant

pytestmark = pytest.mark.integration

NEW_TABLES = (
    "source_records",
    "source_artifacts",
    "source_admissions",
    "automation_corpus_snapshots",
    "automation_workflow_artifacts",
    "automation_pattern_descriptors",
)


async def _second_project(engine: AsyncEngine, tenant_id: UUID) -> UUID:
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
                "slug": f"source-rls-{project_id.hex}",
                "now": now,
            },
        )
        await uow.commit()
    return project_id


async def _source(
    service: SourceService,
    *,
    tenant_id: UUID,
    project_id: UUID,
    provider_key: str,
) -> None:
    await service.ensure_source(
        tenant_id=tenant_id,
        project_id=project_id,
        provider_key=provider_key,
        display_name=provider_key,
        source_domain="AUTOMATION",
        source_class="PUBLIC_REPOSITORY",
        source_kind="EXACT_SNAPSHOT",
        source_trust="S4_MAINTAINED_OSS",
        config={"repository": "Zie619/n8n-workflows"},
    )


@pytest.mark.asyncio
async def test_0040_tables_force_project_and_tenant_rls() -> None:
    engine = new_engine()
    try:
        tenant_a = await seed_tenant(engine)
        project_b = await _second_project(engine, tenant_a.tenant_id)
        tenant_c = await seed_tenant(engine)
        service = SourceService(engine)
        await _source(
            service,
            tenant_id=tenant_a.tenant_id,
            project_id=tenant_a.project_id,
            provider_key="automation:a",
        )
        await _source(
            service,
            tenant_id=tenant_a.tenant_id,
            project_id=project_b,
            provider_key="automation:b",
        )
        await _source(
            service,
            tenant_id=tenant_c.tenant_id,
            project_id=tenant_c.project_id,
            provider_key="automation:c",
        )

        async with engine.connect() as connection:
            rows = await connection.execute(
                text(
                    "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='public' AND c.relname = ANY(:tables)"
                ),
                {"tables": list(NEW_TABLES)},
            )
            by_table = {row[0]: (row[1], row[2]) for row in rows.all()}
            assert set(by_table) == set(NEW_TABLES)
            assert all(enabled and forced for enabled, forced in by_table.values())

        probe_url = await ensure_rls_probe_role(engine)
        probe_engine = create_async_engine(probe_url)
        try:
            async with open_rls_probe(
                probe_engine,
                tenant_id=tenant_a.tenant_id,
                project_id=tenant_a.project_id,
            ) as connection:
                rows = await connection.execute(
                    text("SELECT provider_key FROM source_records ORDER BY provider_key")
                )
                assert [row[0] for row in rows.all()] == ["automation:a"]

            async with open_rls_probe(
                probe_engine,
                tenant_id=tenant_a.tenant_id,
                project_id=project_b,
            ) as connection:
                rows = await connection.execute(
                    text("SELECT provider_key FROM source_records ORDER BY provider_key")
                )
                assert [row[0] for row in rows.all()] == ["automation:b"]

            async with open_rls_probe(
                probe_engine,
                tenant_id=tenant_c.tenant_id,
                project_id=tenant_c.project_id,
            ) as connection:
                rows = await connection.execute(
                    text("SELECT provider_key FROM source_records ORDER BY provider_key")
                )
                assert [row[0] for row in rows.all()] == ["automation:c"]
        finally:
            await probe_engine.dispose()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_0040_vekl_provenance_foreign_keys_target_neutral_sources() -> None:
    engine = new_engine()
    expected = {
        "vekl_resources_source_fkey": "source_records",
        "vekl_resources_artifact_fkey": "source_artifacts",
        "vekl_research_findings_source_fkey": "source_records",
        "vekl_research_findings_artifact_fkey": "source_artifacts",
    }
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(
                text(
                    "SELECT con.conname, ref.relname "
                    "FROM pg_constraint con "
                    "JOIN pg_class ref ON ref.oid=con.confrelid "
                    "WHERE con.conname = ANY(:names)"
                ),
                {"names": list(expected)},
            )
            actual = {row[0]: row[1] for row in rows.all()}
        assert actual == expected
    finally:
        await engine.dispose()
