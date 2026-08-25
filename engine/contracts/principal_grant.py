# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PrincipalGrant(BaseModel):
    """
    Authorization grant for a principal (Chapter 13.9/14.2). grant_scope selects the
    authorization level: ORGANIZATION covers every tenant under the principal's
    organization, TENANT covers one tenant's projects, PROJECT covers exactly one
    project. scope_type is the ABAC constraint class the grant is evaluated under.
    """

    model_config = ConfigDict(extra="forbid")

    grant_id: UUID
    tenant_id: UUID
    project_id: UUID | None = None
    principal_id: UUID
    scope_type: Literal["ORGANIZATION", "PROJECT"]
    grant_scope: Literal["ORGANIZATION", "TENANT", "PROJECT"]
    created_at: datetime
    updated_at: datetime
