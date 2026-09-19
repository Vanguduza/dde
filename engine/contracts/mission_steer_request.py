# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MissionSteerRequest(BaseModel):
    """
    EDR-0019 Epic A live owner steer. A steer is acknowledged immediately and executed
    at a safe boundary: it never races an active repository writer, and it never kills
    active work to take effect. A steer executes under ordinary DDE authority only -- it
    cannot write around TruthService, cannot mutate Project Truth without ordinary
    accepted authority, and cannot silently discard an active ChangePacket. A read-only
    owner question is not a steer and must not serialize writers, which is why read_only
    requests take no barrier.
    """

    model_config = ConfigDict(extra="forbid")

    steer_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    requested_by_principal_id: UUID | None = None
    authority_class: Literal[
        "OWNER_EXPLICIT",
        "OWNER_DERIVED",
        "OWNER_DELEGATED_AUTONOMY",
        "NO_AUTHORITY",
    ]
    read_only: bool
    material: bool
    intent_text_hash: str
    intent_summary: str
    state: Literal[
        "RECEIVED",
        "ACKNOWLEDGED",
        "BARRIER_SET",
        "WAITING_FOR_SAFE_BOUNDARY",
        "SAFE_BOUNDARY_REACHED",
        "AUTHORITY_RECONCILED",
        "EXECUTING",
        "VERIFIED",
        "COMPLETE",
        "FAILED",
        "BLOCKED",
        "SUPERSEDED",
    ]
    disposition: (
        Literal[
            "APPLIED",
            "SUPERSEDED",
            "REJECTED_AUTHORITY",
            "REJECTED_CONFLICT",
            "ABANDONED",
        ]
        | None
    ) = None
    requires_truth_change: bool
    truth_change_ref: str | None = None
    supersedes_steer_id: UUID | None = None
    barrier_id: UUID | None = None
    acknowledged_at: datetime | None = None
    safe_boundary_at: datetime | None = None
    applied_at: datetime | None = None
    evidence_pointer: str | None = None
    decision_hash: str
    created_at: datetime
    updated_at: datetime
