# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ResearchCell(BaseModel):
    """
    The EDR-0019 Epic D coverage unit: DevelopmentUnitRevision x ResearchDimension.
    Coverage is measurable because every cell carries an explicit state; a mission is
    never 'complete' merely because a model answered. NO_USEFUL_EVIDENCE is a real
    terminal outcome and is not failure.
    """

    model_config = ConfigDict(extra="forbid")

    cell_id: UUID
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
    state: Literal[
        "UNSEEDED",
        "QUEUED",
        "FIRST_PASS",
        "ANALYZED",
        "DEEP_EVIDENCE_PENDING",
        "DEEP_EVIDENCE_COMPLETE",
        "CONFLICTED",
        "QUALIFICATION_PENDING",
        "ADMITTED",
        "PARTIALLY_ADMITTED",
        "NO_USEFUL_EVIDENCE",
        "FAILED_RETRYABLE",
        "FAILED_TERMINAL",
        "STALE",
    ]
    attempts: int
    retry_count: int
    last_error_class: str | None = None
    stale_reason: str | None = None
    stale_invalidated_at: datetime | None = None
    first_pass_at: datetime | None = None
    deep_evidence_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
