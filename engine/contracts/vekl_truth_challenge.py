# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VEKLTruthChallenge(BaseModel):
    """
    Governed evidence package proposing an exact target Project Truth delta; cannot
    write truth directly.
    """

    model_config = ConfigDict(extra="forbid")

    challenge_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID | None = None
    challenge_class: Literal[
        "SECURITY_CHALLENGE",
        "COMPATIBILITY_CHALLENGE",
        "ARCHITECTURE_CHALLENGE",
        "PRODUCT_EXPERIENCE_CHALLENGE",
        "REGULATORY_CHALLENGE",
        "PERFORMANCE_CHALLENGE",
        "OPERABILITY_CHALLENGE",
        "COST_CHALLENGE",
        "OPPORTUNITY_CHALLENGE",
    ]
    severity: Literal["INFO", "MATERIAL", "HIGH", "CRITICAL"]
    status: Literal[
        "DISCOVERED",
        "EVIDENCE_QUALIFIED",
        "CONFLICT_CONFIRMED",
        "CHALLENGE_CANDIDATE",
        "REVIEW_REQUIRED",
        "MORE_EVIDENCE_REQUIRED",
        "ACCEPTED",
        "DEFERRED",
        "REJECTED",
        "TRUTH_CHANGE_DRAFTED",
        "TRUTH_CHANGED",
        "STALE",
    ]
    current_truth_hash: str
    evidence: dict[str, object]
    conflict: dict[str, object]
    confidence: dict[str, object]
    impact: dict[str, object]
    proposal: dict[str, object]
    decision_analysis: dict[str, object]
    approval_id: UUID | None = None
    required_role: str
    decision: str | None = None
    decision_reason: str | None = None
    decided_at: datetime | None = None
    reopen_conditions: list[str]
    challenge_hash: str
    created_at: datetime
    updated_at: datetime
