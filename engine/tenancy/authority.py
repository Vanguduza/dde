"""Tenancy authority (Chapter 13.9, DDE-051).

The scope chain is `Principal -> Organization/Tenant -> Project -> Mission
-> Task -> runtime bindings`. This module owns the authorization half of it:

- `resolve_principal_tenant` derives tenant identity from the
  authenticated principal row -- never from a client-supplied target id.
  The gateway session service already calls `PrincipalLookup` for this;
  this service is the authority behind that lookup and the writer of the
  grant rows the gateway checks.
- `authorize_project_access` verifies a principal holds a grant covering
  the target project (PROJECT grant, TENANT grant, or ORGANIZATION grant
  through `tenants.organization_id`) BEFORE any domain or resource
  operation. Fail-closed: unknown principal -> INVALID_CREDENTIALS, no
  covering grant -> TENANT_SCOPE_VIOLATION.

Writes go through a caller-supplied unit of work so grant creation shares
the caller's transaction (Chapter 3.5); reads open their own short-lived
connection because identity resolution must run before any tenant GUC is
set (Chapter 13.9).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.tenancy.grants import GrantScopeType
from engine.truth.db import PostgresUnitOfWork


class TenancyAuthorityService:
    """Authorization authority over `principals` / `principal_grants`
    (Chapter 13.9). The gateway consumes its verdicts; nothing else writes
    grant rows."""

    def __init__(self, engine: AsyncEngine, clock: Clock | None = None) -> None:
        self._engine = engine
        self._clock = clock or SystemClock()

    async def resolve_principal_tenant(self, *, principal_id: UUID) -> UUID:
        """Tenant of an authenticated principal, resolved from `principals`.

        Raises INVALID_CREDENTIALS for an unknown principal -- callers must
        never accept a tenant id from the wire when this can answer instead.
        """
        async with self._engine.connect() as connection:
            row = (
                await connection.execute(
                    text("SELECT tenant_id FROM principals WHERE principal_id = :pid"),
                    {"pid": principal_id},
                )
            ).first()
        if row is None:
            raise DdeError(
                "INVALID_CREDENTIALS",
                "Unknown principal",
                details={"principal_id": str(principal_id)},
            )
        return UUID(str(row[0]))

    async def authorize_project_access(
        self,
        *,
        principal_id: UUID,
        tenant_id: UUID,
        project_id: UUID,
    ) -> None:
        """Verify the principal is authorized for `(tenant_id, project_id)`
        before any domain operation (Chapter 13.9).

        Grant coverage:
        - a PROJECT grant on exactly this project under this tenant;
        - a TENANT-scope grant (project_id NULL) on this tenant;
        - an ORGANIZATION grant whose organization owns this tenant.
        """
        async with self._engine.connect() as connection:
            principal_row = (
                await connection.execute(
                    text(
                        "SELECT p.tenant_id FROM principals p "
                        "WHERE p.principal_id = :pid"
                    ),
                    {"pid": principal_id},
                )
            ).first()
        if principal_row is None:
            raise DdeError(
                "INVALID_CREDENTIALS",
                "Unknown principal",
                details={"principal_id": str(principal_id)},
            )
        principal_home_tenant = UUID(str(principal_row[0]))
        if principal_home_tenant != tenant_id:
            # Same-organization sibling tenants are still reachable, but only
            # through an ORGANIZATION grant (checked below); a principal whose
            # home tenant IS the requested tenant passes straight to grant
            # checks. Anything else fails before grants are read.
            same_organization = await self._shares_organization(
                home_tenant_id=principal_home_tenant, target_tenant_id=tenant_id
            )
            if not same_organization:
                raise DdeError(
                    "TENANT_SCOPE_VIOLATION",
                    "Principal belongs to another organization",
                    details={
                        "principal_tenant_id": str(principal_row[0]),
                        "requested_tenant_id": str(tenant_id),
                    },
                )

        async with self._engine.connect() as connection:
            covered = (
                await connection.execute(
                    text(
                        "SELECT 1 FROM principal_grants g "
                        "WHERE g.tenant_id = :tid "
                        "AND g.principal_id = :pid "
                        "AND ("
                        "  g.grant_scope = 'TENANT'"
                        "  OR (g.grant_scope = 'PROJECT' "
                        "      AND g.project_id = :proj)"
                        ") LIMIT 1"
                    ),
                    {"tid": tenant_id, "pid": principal_id, "proj": project_id},
                )
            ).first()

        # An ORGANIZATION grant covers the whole organization: evaluate it
        # explicitly rather than in one opaque SQL blob.
        if covered is None:
            org_granted = await self._organization_grant_covers(
                tenant_id=tenant_id, principal_id=principal_id
            )
            if not org_granted:
                raise DdeError(
                    "TENANT_SCOPE_VIOLATION",
                    "Principal is not authorized for the target project",
                    details={"project_id": str(project_id)},
                )

    async def _shares_organization(
        self, *, home_tenant_id: UUID, target_tenant_id: UUID
    ) -> bool:
        """True when two tenants belong to the same organization (Ch.13.9
        scope chain). Cross-organization access is refused outright."""
        async with self._engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT 1 FROM tenants home, tenants target "
                        "WHERE home.tenant_id = :home "
                        "AND target.tenant_id = :target "
                        "AND home.organization_id = target.organization_id "
                        "LIMIT 1"
                    ),
                    {"home": home_tenant_id, "target": target_tenant_id},
                )
            ).first()
        return row is not None

    async def _organization_grant_covers(
        self, *, tenant_id: UUID, principal_id: UUID
    ) -> bool:
        async with self._engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT 1 FROM principal_grants g "
                        "JOIN tenants requested ON requested.tenant_id = :tid "
                        "WHERE g.principal_id = :pid "
                        "AND g.grant_scope = 'ORGANIZATION' "
                        "AND EXISTS ("
                        "  SELECT 1 FROM principals p "
                        "  JOIN tenants home ON home.tenant_id = p.tenant_id "
                        "  WHERE p.principal_id = g.principal_id "
                        "  AND home.organization_id "
                        "      = requested.organization_id"
                        ") LIMIT 1"
                    ),
                    {"tid": tenant_id, "pid": principal_id},
                )
            ).first()
        return row is not None

    async def record_project_grant(
        self,
        uow: PostgresUnitOfWork,
        *,
        principal_id: UUID,
        project_id: UUID | None,
        grant_scope_type: GrantScopeType = GrantScopeType.PROJECT,
    ) -> UUID:
        """Insert one grant row inside the caller's unit of work.

        `grant_scope` follows the scope_type default (ORGANIZATION ->
        ORGANIZATION-wide, PROJECT -> exact project); a TENANT-scope grant
        passes `project_id=None` with the PROJECT scope type.
        """
        grant_id = uuid7()
        now = self._clock.now()
        await uow.connection.execute(
            text(
                "INSERT INTO principal_grants (grant_id, tenant_id, project_id, "
                "principal_id, scope_type, grant_scope, created_at, updated_at) "
                "SELECT :gid, p.tenant_id, :proj, :pid, :stype, :gscope, :now, :now "
                "FROM principals p WHERE p.principal_id = :pid"
            ),
            {
                "gid": grant_id,
                "proj": project_id
                if grant_scope_type is GrantScopeType.PROJECT
                else None,
                "pid": principal_id,
                "stype": grant_scope_type.value,
                "gscope": (
                    "ORGANIZATION"
                    if grant_scope_type is GrantScopeType.ORGANIZATION
                    else "PROJECT"
                ),
                "now": now,
            },
        )
        return grant_id
