# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Principal(BaseModel):
    """Authenticated actor identity."""

    model_config = ConfigDict(extra="forbid")

    principal_id: UUID
    tenant_id: UUID
    slug: str
    created_at: datetime
    updated_at: datetime
