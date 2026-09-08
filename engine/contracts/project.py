# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Project(BaseModel):
    """Project identity scoped to a tenant."""

    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    tenant_id: UUID
    slug: str
    kind: Literal["TARGET_APPLICATION", "DDE_CONTROL_PLANE"] | None = None
    created_at: datetime
    updated_at: datetime
