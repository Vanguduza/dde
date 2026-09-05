# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AiAutomation(BaseModel):
    """
    Durable one-time/interval/cron/condition DDE conversation automation. Due work re-
    enters governed commands.
    """

    model_config = ConfigDict(extra="forbid")

    automation_id: UUID
    tenant_id: UUID
    project_id: UUID
    conversation_id: UUID
    mission_id: UUID | None = None
    name: str
    schedule_kind: Literal["ONCE", "INTERVAL", "CRON", "CONDITION"]
    schedule_expression: str
    timezone: str
    action_kind: Literal[
        "CHAT_PROMPT",
        "COMMAND",
        "VERIFICATION",
        "SCREEN_AUDIT",
        "RESEARCH",
    ]
    action_payload: dict[str, object]
    state: Literal["ACTIVE", "PAUSED", "COMPLETED", "CANCELLED", "BLOCKED"]
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    last_result_ref: str | None = None
    run_count: int
    created_by: UUID | None = None
    lock_version: int
    created_at: datetime
    updated_at: datetime
