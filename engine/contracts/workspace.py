# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Workspace(BaseModel):
    """
    Isolated worktree bound to an environment. Optimistic locking required by Chapter
    3.5.
    """

    model_config = ConfigDict(extra="forbid")

    workspace_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    base_revision: str | None = None
    lock_version: int
    created_at: datetime
    updated_at: datetime
