# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
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
    task_id: UUID | None = None
    execution_environment_id: UUID | None = None
    base_revision: str | None = None
    current_revision: str | None = None
    workspace_path: str | None = None
    policy: dict[str, object]
    status: Literal["PROVISIONING", "READY", "IN_USE", "CLEANED_UP", "FAILED"]
    lock_version: int
    created_at: datetime
    updated_at: datetime
