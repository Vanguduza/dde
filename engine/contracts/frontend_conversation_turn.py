# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FrontendConversationTurn(BaseModel):
    """
    DDE-069 one turn in a Frontend Conversation, append-only. Owned by
    engine.studio.chat. A turn records the classified intent, the context it was
    resolved against and the ids of whatever it produced -- mutations, a design request,
    a read -- so the lineage from an instruction to the change it caused is
    reconstructable. A turn that was refused records why: an ambiguous reference and an
    unavailable provider are different answers and the user needs to see which one they
    got.
    """

    model_config = ConfigDict(extra="forbid")

    turn_id: UUID
    tenant_id: UUID
    project_id: UUID
    conversation_id: UUID
    sequence: int
    role: Literal["user", "studio"]
    text: str
    intent: str
    outcome: Literal["ROUTED", "REFUSED", "ANSWERED"]
    refusal_code: str | None = None
    refusal_detail: str | None = None
    resolved_context: dict[str, object]
    produced_refs: list[str]
    created_at: datetime
    updated_at: datetime
    attachment_ids: list[UUID]
    plan_id: UUID | None = None
    model_profile_id: str | None = None
