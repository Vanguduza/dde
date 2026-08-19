# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PrincipalGrant(BaseModel):
    """Authorization grant for a principal."""

    model_config = ConfigDict(extra="forbid")

    grant_id: UUID
    tenant_id: UUID
    project_id: UUID | None = None
    principal_id: UUID
    created_at: datetime
    updated_at: datetime
