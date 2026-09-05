# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AiHook(BaseModel):
    """
    Governed conversation/provider/tool lifecycle hook. Hooks propose actions and cannot
    bypass Gateway authority.
    """

    model_config = ConfigDict(extra="forbid")

    hook_id: UUID
    tenant_id: UUID
    project_id: UUID
    conversation_id: UUID | None = None
    name: str
    event_kind: Literal[
        "BEFORE_TURN",
        "AFTER_TURN",
        "BEFORE_CONTEXT",
        "AFTER_CONTEXT",
        "BEFORE_PROVIDER",
        "AFTER_PROVIDER",
        "BEFORE_TOOL",
        "AFTER_TOOL",
        "BEFORE_MUTATION",
        "AFTER_MUTATION",
        "BEFORE_VERIFICATION",
        "AFTER_VERIFICATION",
        "BEFORE_PROMOTION",
        "BEFORE_COMPACTION",
        "AFTER_COMPACTION",
        "SESSION_START",
        "SESSION_END",
        "SUBAGENT_START",
        "SUBAGENT_END",
    ]
    action_kind: Literal[
        "RECORD_ACTIVITY",
        "CREATE_CHECKPOINT",
        "PROPOSE_MEMORY",
        "PROPOSE_COMMAND",
        "RUN_SKILL",
    ]
    condition: dict[str, object]
    action_payload: dict[str, object]
    state: Literal["ACTIVE", "PAUSED", "DISABLED"]
    last_triggered_at: datetime | None = None
    trigger_count: int
    created_by: UUID | None = None
    lock_version: int
    created_at: datetime
    updated_at: datetime
