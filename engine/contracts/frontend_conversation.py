# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FrontendConversation(BaseModel):
    """
    DDE-069 the Frontend Studio's single conversational control plane. Owned by
    engine.studio.chat. Frontend Chat is not a chatbot dock bolted onto the studio: it
    carries the workspace context (screen, candidate, selection, viewport) that makes a
    reference like "this" or "Candidate B" resolvable, and every turn that changes
    frontend state compiles to the same governed FrontendMutation or DesignSession
    operation as any other affordance. `/design` is a capability inside this
    conversation, not a second one.
    """

    model_config = ConfigDict(extra="forbid")

    conversation_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    active_candidate_id: UUID | None = None
    design_session_id: UUID | None = None
    selected_node_keys: list[str]
    viewport: str
    lock_version: int
    created_at: datetime
    updated_at: datetime
