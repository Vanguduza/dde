# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ResearchConflict(BaseModel):
    """
    A detected contradiction between research findings, or between a finding and Project
    Truth. A conflict never resolves itself by majority or recency: an implementation
    conflict with Project Truth remains rejected and may only be escalated through the
    existing governed VEKLTruthChallenge path.
    """

    model_config = ConfigDict(extra="forbid")

    conflict_id: UUID
    tenant_id: UUID
    project_id: UUID
    research_mission_id: UUID
    unit_revision: str
    dimension: Literal[
        "ARCHITECTURE",
        "OFFICIAL_DOCUMENTATION",
        "CURRENT_RELEASES",
        "SECURITY",
        "FAILURE_MODES",
        "TESTING",
        "PERFORMANCE",
        "DEPLOYMENT",
        "INTEGRATION",
        "UX",
        "FRONTEND_QUALITY",
        "ACCESSIBILITY",
        "SOURCE_INTELLIGENCE",
        "CONTRADICTIONS",
        "ANTI_PATTERNS",
        "WORKFLOW_AUTOMATION",
        "OBSERVABILITY",
        "COMPATIBILITY_MIGRATION",
    ]
    conflict_class: Literal[
        "EVIDENCE_DISAGREEMENT",
        "VERSION_DISAGREEMENT",
        "TRUTH_CONFLICT",
        "SECURITY_DISAGREEMENT",
        "POLARITY_DISAGREEMENT",
    ]
    finding_a_ref: str
    finding_b_ref: str | None = None
    project_truth_ref: str | None = None
    status: Literal[
        "OPEN",
        "CORROBORATED",
        "RESOLVED_BY_EVIDENCE",
        "ESCALATED_TRUTH_CHALLENGE",
        "REJECTED",
        "SUPERSEDED",
    ]
    truth_challenge_id: UUID | None = None
    resolution_note: str | None = None
    detected_at: datetime
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
