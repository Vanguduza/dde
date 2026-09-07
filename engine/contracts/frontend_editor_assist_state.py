# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FrontendEditorAssistState(BaseModel):
    """
    DDE-069 project editor-assist policy. Auto Layout constrains deterministic direct
    manipulation; AI Suggest enables passive non-authoritative suggestions only. Neither
    state authorizes mutation or auto-application.
    """

    model_config = ConfigDict(extra="forbid")

    assist_state_id: UUID
    tenant_id: UUID
    project_id: UUID
    auto_layout: bool
    ai_suggest: bool
    updated_by: UUID
    lock_version: int
    created_at: datetime
    updated_at: datetime
