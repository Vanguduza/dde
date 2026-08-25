"""Chapter 13.9/14.2 grant model for `principal_grants`.

`grant_scope` selects the authorization level of a grant row:

- ORGANIZATION: covers every tenant under the principal's organization
  (the row's tenant_id anchors it to one tenant for RLS; the coverage set
  is derived through tenants.organization_id).
- TENANT: covers every project of the row's own tenant (project_id NULL).
- PROJECT: covers exactly one project.

`scope_type` is the ABAC constraint class the gateway evaluates the grant
under today (ORGANIZATION or PROJECT); it is recorded on every row so a
future policy engine can extend the constraint vocabulary without another
migration.
"""

from __future__ import annotations

from enum import StrEnum


class GrantScopeType(StrEnum):
    """ABAC constraint class of a grant (Chapter 14.2)."""

    ORGANIZATION = "ORGANIZATION"
    PROJECT = "PROJECT"
