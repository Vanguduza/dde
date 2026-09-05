# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FrontendChatCheckpoint(BaseModel):
    """
    DDE-069 universal DDE Chat checkpoint for conversation/workspace context and
    branch/recovery. Distinct from WorkerRun recovery Checkpoint and never substitutes
    for it.
    """

    model_config = ConfigDict(extra="forbid")

    checkpoint_id: UUID
    tenant_id: UUID
    project_id: UUID
    conversation_id: UUID
    turn_sequence: int
    mode: Literal["ASK", "PLAN", "EXECUTE"]
    model_profile_id: str | None = None
    plan_id: UUID | None = None
    workspace_id: UUID | None = None
    pinned_context_refs: list[str]
    attachment_refs: list[UUID]
    workspace_revision: str | None = None
    diff_hash: str | None = None
    context_hash: str
    note: str | None = None
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
    conversation_context: dict[str, object] | None = None
