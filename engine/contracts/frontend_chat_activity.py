# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FrontendChatActivity(BaseModel):
    """
    DDE-069 append-only operator-visible Chat/model/tool/command activity. Tool
    execution is never hidden inside assistant prose.
    """

    model_config = ConfigDict(extra="forbid")

    activity_id: UUID
    tenant_id: UUID
    project_id: UUID
    conversation_id: UUID
    sequence: int
    turn_id: UUID | None = None
    plan_id: UUID | None = None
    workspace_id: UUID | None = None
    command_id: UUID | None = None
    kind: Literal[
        "MODEL_REQUEST",
        "MODEL_RESPONSE",
        "CONTEXT_ASSEMBLED",
        "TOOL_PROPOSED",
        "TOOL_STARTED",
        "TOOL_RESULT",
        "COMMAND_ACCEPTED",
        "COMMAND_FAILED",
        "PLAN_CREATED",
        "PLAN_STEP",
        "ATTACHMENT_ADDED",
        "CHECKPOINT_CREATED",
        "CHECKPOINT_RESTORED",
        "DIFF_REFRESHED",
        "FILE_REVERTED",
        "VERIFICATION_STARTED",
        "VERIFICATION_RESULT",
        "ERROR",
        "STATUS",
    ]
    state: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", "BLOCKED"]
    label: str
    detail: str | None = None
    refs: dict[str, object]
    cancellable: bool
    cancel_reason: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
