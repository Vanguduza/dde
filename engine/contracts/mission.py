# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Mission(BaseModel):
    """Manufacturing mission. Optimistic locking required by Chapter 3.5."""

    model_config = ConfigDict(extra="forbid")

    mission_id: UUID
    tenant_id: UUID
    project_id: UUID
    slug: str
    status: str
    autonomy_ceiling: int
    lock_version: int
    created_at: datetime
    updated_at: datetime
