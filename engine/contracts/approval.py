# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Approval(BaseModel):
    """
    Chapter 13.1 Approval -- bound to an exact plan/action by scope_hash and not
    reusable for a materially different plan. Owned by engine.governance (Chapter 3.8).
    tenant_id/project_id are required by Chapter 3.2 even though 13.1's field sketch
    omits them. standing_id records overnight pre-authorization (13.2). command_id is
    CommandLedger identity (Chapter 12.5). edr_id is set when a decision becomes an EDR
    (13.3.5). human_minutes feeds the Chapter 13.4 attention budget. Parking on EXPIRED
    is a mission lifecycle change, not a second status on this row.
    """

    model_config = ConfigDict(extra="forbid")

    approval_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID | None = None
    approval_type: str
    scope_hash: str
    requested_by: UUID
    required_role: str
    evidence_refs: list[str]
    suggested_decision: str | None = None
    status: str
    decided_by: UUID | None = None
    decided_at: datetime | None = None
    expires_at: datetime | None = None
    rationale: str | None = None
    standing_id: UUID | None = None
    edr_id: UUID | None = None
    human_minutes: float
    command_id: UUID
    created_at: datetime
    updated_at: datetime
