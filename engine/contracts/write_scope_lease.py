# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WriteScopeLease(BaseModel):
    """
    Chapter 10.3's structural conflict prevention: reserved by the Task Planner before
    scheduling, owned by engine.integration. Status only is mutable; scope_patterns are
    immutable once reserved.
    """

    model_config = ConfigDict(extra="forbid")

    lease_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID
    scope_patterns: list[str]
    exclusive: bool
    status: str
    acquired_at: datetime
    expires_at: datetime
    released_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
