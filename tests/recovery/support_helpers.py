"""Shared PostgreSQL helpers for the Chapter 11.5 invariant suites.

Kept separate from the test modules so the recovery suite and the
postgres service suite exercise exactly one fixture path.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.product_env.service import HUMAN_ORIGIN, ProductEnvironmentService
from engine.truth.db import build_engine, open_unit_of_work
from tests.support.db import ensure_rls_probe_role


async def ready_environment(engine: AsyncEngine, tenant) -> object:
    """A READY ephemeral_preview whose datastore is this test database."""
    product_envs = ProductEnvironmentService(engine)
    record = await product_envs.provision(
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        env_class="ephemeral_preview",
        source_revision="abc1234",
        build_artifact_ref="r2://artifacts/build.tar.gz",
        runtime_topology_ref={"compose": "docker-compose.yml"},
        datastore_ref="throwaway",
        requested_by_origin=HUMAN_ORIGIN,
        ttl_seconds=3600,
    )
    migrated = await product_envs.apply_migrations_forward(
        record, empty_verified=True, previous_verified=True
    )
    seeded = await product_envs.seed(
        migrated,
        slug="erp-baseline",
        content_hash="cafe1234",
        artifact_ref="r2://seeds/erp-baseline-v1.sql",
        created_by="principal-1",
    )
    return await product_envs.mark_ready(seeded)


_PLANT_STATEMENT_PREFIXES = ("dup-stmt-", "fin-stmt-")


async def purge_planted_requirements(engine: AsyncEngine) -> None:
    """Remove requirement rows planted by any earlier run of these suites,
    from any tenant/project.

    Must run as the table OWNER: the probe role is RLS-limited to one
    project and physically cannot see -- let alone delete -- rows another
    run's tenant left behind. The predicate layer likewise reads the
    datastore as its owner (in production a throwaway per-environment
    database; here the shared dev database), so any leftover planted row
    would leak into every later evaluation. The planted statement
    prefixes belong exclusively to these suites.
    """
    async with engine.begin() as conn:
        await conn.execute(  # type: ignore[attr-defined]
            text(
                "DELETE FROM requirements WHERE statement LIKE :p1 "
                "OR statement LIKE :p2"
            ),
            {
                "p1": f"{_PLANT_STATEMENT_PREFIXES[0]}%",
                "p2": f"{_PLANT_STATEMENT_PREFIXES[1]}%",
            },
        )


async def plant_duplicate_requirements(
    engine: AsyncEngine, tenant, *, statement: str
) -> None:
    """Two requirement rows sharing (project_id, statement) in THIS
    tenant -- a genuine violation of a statement-uniqueness invariant.
    Slugs stay distinct because the schema itself enforces
    `UNIQUE (project_id, slug)`; the invariant under test guards the rule
    the schema deliberately leaves to the engine."""
    await purge_planted_requirements(engine)
    probe_url = await ensure_rls_probe_role(engine)
    probe_engine = build_engine(probe_url)
    try:
        async with open_unit_of_work(
            probe_engine, tenant_id=tenant.tenant_id, project_id=tenant.project_id
        ) as uow:
            for _ in range(2):
                await uow.connection.execute(
                    text(
                        "INSERT INTO requirements (requirement_id, tenant_id, "
                        "project_id, slug, statement, constraints, "
                        "acceptance_conditions, status, created_at, updated_at) "
                        "VALUES (:rid, :tid, :pid, :slug, :stmt, '{}', '{}', "
                        "'draft', now(), now())"
                    ),
                    {
                        "rid": uuid4(),
                        "tid": tenant.tenant_id,
                        "pid": tenant.project_id,
                        "slug": f"req-{uuid4().hex[:12]}",
                        "stmt": statement,
                    },
                )
            await uow.commit()
    finally:
        await probe_engine.dispose()


async def repair_requirements(engine: AsyncEngine, tenant, *, statement: str) -> None:
    """The repair task's real work: remove the duplicate rows through the
    same committing RLS-scoped path."""
    probe_url = await ensure_rls_probe_role(engine)
    probe_engine = build_engine(probe_url)
    try:
        async with open_unit_of_work(
            probe_engine, tenant_id=tenant.tenant_id, project_id=tenant.project_id
        ) as uow:
            await uow.connection.execute(
                text(
                    "DELETE FROM requirements WHERE project_id = :pid "
                    "AND statement = :stmt"
                ),
                {"pid": tenant.project_id, "stmt": statement},
            )
            await uow.commit()
    finally:
        await probe_engine.dispose()
