"""PostgreSQL test helpers for engine.truth (Chapter 19.1 schema/recovery tests).

Seeds the minimal `tenants` / `projects` / `principals` rows that
`product_constitution_versions`, `requirements` and `edrs` foreign-key against,
using the same fail-closed RLS path production code goes through.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.core.ids import uuid7
from engine.gateway.settings import get_settings
from engine.truth.db import build_engine, open_unit_of_work

RLS_PROBE_ROLE = "dde_rls_probe"
RLS_PROBE_PASSWORD = "dde_rls_probe"  # noqa: S105 -- local test-only role, not a secret


@dataclass
class TenantFixture:
    tenant_id: UUID
    project_id: UUID
    principal_id: UUID


def new_engine() -> AsyncEngine:
    """One engine per test, standing in for one process's connection pool."""
    return build_engine(get_settings().database_url)


async def ensure_rls_probe_role(engine: AsyncEngine) -> str:
    """Idempotently create a non-superuser, non-bypassrls role and return its
    database URL.

    The local dev `dde` role (Chapter 3.2 setup script) is a superuser and
    therefore always bypasses row-level security regardless of `FORCE ROW LEVEL
    SECURITY`; RLS enforcement is only observable through a role that isn't.
    Production deployments must never grant the application role BYPASSRLS.
    """
    async with engine.connect() as connection:
        exists = await connection.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
            {"role": RLS_PROBE_ROLE},
        )
        if exists.first() is None:
            # Role name/password are fixed local constants, not user input.
            await connection.execute(
                text(
                    f"CREATE ROLE {RLS_PROBE_ROLE} LOGIN PASSWORD "  # noqa: S608
                    f"'{RLS_PROBE_PASSWORD}' NOSUPERUSER NOBYPASSRLS"
                )
            )
        await connection.execute(
            text(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {RLS_PROBE_ROLE}")
        )
        await connection.commit()
    probe_url = make_url(get_settings().database_url).set(
        username=RLS_PROBE_ROLE, password=RLS_PROBE_PASSWORD
    )
    return probe_url.render_as_string(hide_password=False)


async def truncate_outbox(engine: AsyncEngine) -> None:
    """Clear the `outbox` table before a test that asserts on the
    dispatcher's global drain behaviour.

    The outbox dispatcher deliberately drains across every tenant (Chapter
    17.1: it is a system-level process, not a tenant-scoped request
    handler), so a test asserting an exact published count or event
    identity must not share the table with pending rows any other test
    left behind. `outbox` carries no inbound foreign keys, so truncating it
    alone is safe.
    """
    async with engine.connect() as connection:
        await connection.execute(text("TRUNCATE TABLE outbox"))
        await connection.commit()


async def seed_tenant(engine: AsyncEngine) -> TenantFixture:
    """Insert a fresh tenant/project/principal scoped to their own GUC."""
    tenant_id = uuid7()
    project_id = uuid7()
    principal_id = uuid7()
    now = datetime.now(UTC)
    async with open_unit_of_work(
        engine, tenant_id=tenant_id, project_id=project_id
    ) as uow:
        await uow.connection.execute(
            text(
                "INSERT INTO tenants (tenant_id, slug, created_at, updated_at) "
                "VALUES (:tenant_id, :slug, :now, :now)"
            ),
            {"tenant_id": tenant_id, "slug": f"tenant-{tenant_id.hex}", "now": now},
        )
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
        await uow.connection.execute(
            text(
                "INSERT INTO principals "
                "(principal_id, tenant_id, slug, created_at, updated_at) "
                "VALUES (:principal_id, :tenant_id, :slug, :now, :now)"
            ),
            {
                "principal_id": principal_id,
                "tenant_id": tenant_id,
                "slug": f"principal-{principal_id.hex}",
                "now": now,
            },
        )
        await uow.commit()
    return TenantFixture(
        tenant_id=tenant_id, project_id=project_id, principal_id=principal_id
    )
