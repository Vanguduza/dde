# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProductConstitutionVersion(BaseModel):
    """Versioned Product Constitution record."""

    model_config = ConfigDict(extra="forbid")

    version_id: UUID
    tenant_id: UUID
    project_id: UUID
    version: int
    created_at: datetime
    updated_at: datetime
