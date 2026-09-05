# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FrontendConversation(BaseModel):
    """
    DDE-069 DDE Code / Frontend Studio durable AI conversation control plane. Owned by
    engine.studio.chat. It carries explicit project/workspace/frontend context, Cursor-
    class Ask/Plan/Execute mode, model selection, branch lineage and pinned references.
    A model is replaceable; DDE owns history, authority, plans and evidence.
    """

    model_config = ConfigDict(extra="forbid")

    conversation_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    active_candidate_id: UUID | None = None
    design_session_id: UUID | None = None
    screen_key: str | None = None
    selected_node_keys: list[str]
    viewport: str
    title: str | None = None
    status: Literal["OPEN", "ARCHIVED"]
    mode: Literal["ASK", "PLAN", "EXECUTE"]
    model_profile_id: str | None = None
    active_workspace_id: UUID | None = None
    active_plan_id: UUID | None = None
    parent_conversation_id: UUID | None = None
    branched_from_turn_id: UUID | None = None
    pinned_context_refs: list[str]
    created_by: UUID | None = None
    archived_at: datetime | None = None
    lock_version: int
    created_at: datetime
    updated_at: datetime
