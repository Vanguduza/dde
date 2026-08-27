"""Chapter 17.5 isolated restore: real restore into a scratch database.

`IsolatedRestoreService.restore_tenant` is the production mutation: it
creates a throwaway database, applies migrations to head, copies the
tenant's control-plane rows (organization, tenant, project, audit_events),
and runs `AuditService.verify_chain` against the restored copy. PostgreSQL
PITR / WAL archiving is inspected, not enforced — local and CI Postgres
run with `archive_mode=off` (EDR-0033).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import alembic.command
import alembic.config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from engine.audit.repository import AuditRepository
from engine.audit.service import AuditService
from engine.contracts.audit_event import AuditEvent
from engine.core.errors import DdeError
from engine.core.ids import uuid7

_SAFE_IDENT = re.compile(r"^[a-z][a-z0-9_]*$")
_IDENTITY_TABLES = (
    ("organizations", "organization_id = :organization_id"),
    ("tenants", "tenant_id = :tenant_id"),
    ("projects", "project_id = :project_id"),
)


@dataclass(frozen=True)
class PitrStatus:
    archive_mode: str
    wal_level: str

    @property
    def rpo_control_present(self) -> bool:
        return self.archive_mode == "on" and self.wal_level in {
            "replica",
            "logical",
        }


@dataclass(frozen=True)
class IsolatedRestoreResult:
    scratch_database: str
    audit_events_restored: int
    chain_verified: bool
    pitr: PitrStatus


def _make_url(base_url: str, database: str) -> str:
    if "/" not in base_url:
        raise ValueError("database_url must contain a database segment")
    prefix, _, _ = base_url.rpartition("/")
    return f"{prefix}/{database}"


def _require_ident(name: str) -> str:
    if _SAFE_IDENT.fullmatch(name) is None:
        raise DdeError(
            "POLICY_DENIED",
            "scratch database name is not a safe identifier",
            details={"database": name},
        )
    return name


class IsolatedRestoreService:
    """Logical restore of one tenant into an isolated PostgreSQL database."""

    def __init__(self, admin_engine: AsyncEngine) -> None:
        self._admin_engine = admin_engine
        self._database_url = admin_engine.url.render_as_string(hide_password=False)

    async def inspect_pitr(self) -> PitrStatus:
        """Read-only probe of WAL/archive settings. Not a mutation."""
        async with self._admin_engine.connect() as connection:
            archive_mode = str(
                (await connection.execute(text("SHOW archive_mode"))).scalar_one()
            )
            wal_level = str(
                (await connection.execute(text("SHOW wal_level"))).scalar_one()
            )
        return PitrStatus(archive_mode=archive_mode, wal_level=wal_level)

    async def restore_tenant(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
    ) -> IsolatedRestoreResult:
        pitr = await self.inspect_pitr()
        database = _require_ident(
            f"dde_drill_{datetime.now(UTC).strftime('%H%M%S')}_{uuid7().hex[:8]}"
        )
        await self._create_database(database)
        scratch = create_async_engine(_make_url(self._database_url, database))
        try:
            async with scratch.connect() as connection:
                await connection.run_sync(self._upgrade_head)
            copied = await self._copy_tenant(
                tenant_id=tenant_id, project_id=project_id, scratch=scratch
            )
            await AuditService(scratch).verify_chain(tenant_id=tenant_id)
        finally:
            await scratch.dispose()
            await self._drop_database(database)
        return IsolatedRestoreResult(
            scratch_database=database,
            audit_events_restored=copied,
            chain_verified=True,
            pitr=pitr,
        )

    def _upgrade_head(self, connection) -> None:  # type: ignore[no-untyped-def]
        config = alembic.config.Config("alembic.ini")
        config.set_main_option("script_location", "migrations")
        config.attributes["connection"] = connection
        alembic.command.upgrade(config, "head")

    async def _create_database(self, database: str) -> None:
        ident = _require_ident(database)
        async with self._admin_engine.connect() as connection:
            autocommit = await connection.execution_options(
                isolation_level="AUTOCOMMIT"
            )
            await autocommit.execute(text(f'CREATE DATABASE "{ident}"'))  # noqa: S608

    async def _drop_database(self, database: str) -> None:
        ident = _require_ident(database)
        async with self._admin_engine.connect() as connection:
            autocommit = await connection.execution_options(
                isolation_level="AUTOCOMMIT"
            )
            await autocommit.execute(
                text(f'DROP DATABASE IF EXISTS "{ident}" WITH (FORCE)')  # noqa: S608
            )

    async def _copy_tenant(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        scratch: AsyncEngine,
    ) -> int:
        async with self._admin_engine.connect() as source:
            organization_id = (
                await source.execute(
                    text(
                        "SELECT organization_id FROM tenants "
                        "WHERE tenant_id = :tenant_id"
                    ),
                    {"tenant_id": tenant_id},
                )
            ).scalar_one()
            params = {
                "organization_id": organization_id,
                "tenant_id": tenant_id,
                "project_id": project_id,
            }
            identity_rows: dict[str, list[dict[str, object]]] = {}
            for table, where_clause in _IDENTITY_TABLES:
                result = await source.execute(
                    text(f"SELECT * FROM {table} WHERE {where_clause}"),  # noqa: S608
                    params,
                )
                identity_rows[table] = [dict(row) for row in result.mappings().all()]
            audit_rows = (
                (
                    await source.execute(
                        text(
                            "SELECT * FROM audit_events WHERE tenant_id = :tenant_id "
                            "ORDER BY sequence"
                        ),
                        {"tenant_id": tenant_id},
                    )
                )
                .mappings()
                .all()
            )

        async with scratch.begin() as dest:
            for table, _where in _IDENTITY_TABLES:
                for row in identity_rows[table]:
                    columns = list(row.keys())
                    col_sql = ", ".join(columns)
                    placeholders = ", ".join(f":{name}" for name in columns)
                    await dest.execute(
                        text(
                            f"INSERT INTO {table} ({col_sql}) "  # noqa: S608
                            f"VALUES ({placeholders})"
                        ),
                        row,
                    )
            repository = AuditRepository()
            for mapping in audit_rows:
                payload: dict[str, object] = {
                    str(key): value for key, value in mapping.items()
                }
                await repository.insert(dest, AuditEvent.model_validate(payload))
        return len(audit_rows)
