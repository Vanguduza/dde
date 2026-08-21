# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AttentionItem(BaseModel):
    """
    Durable attention-budget identity for Chapter 13.3.4 (expiry raises an attention
    item) and Chapter 13.4 (attention debt is open items older than their SLA). This is
    not the Mission Control projection (DDE-028); it is the governance write that
    projection will read. Owned by engine.governance.
    """

    model_config = ConfigDict(extra="forbid")

    attention_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    kind: str
    summary: str
    status: str
    approval_id: UUID | None = None
    standing_id: UUID | None = None
    sla_due_at: datetime
    opened_at: datetime
    acknowledged_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
