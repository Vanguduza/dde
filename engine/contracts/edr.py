# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Edr(BaseModel):
    """Engineering Decision Record. Accepted records are superseded, never rewritten."""

    model_config = ConfigDict(extra="forbid")

    edr_id: UUID
    tenant_id: UUID
    project_id: UUID
    slug: str
    created_at: datetime
    updated_at: datetime
