# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FrontendCandidateScore(BaseModel):
    """
    DDE-069 M8 explainable candidate score snapshot. UNSCORED/BLOCKED are first-class
    and hard_failures dominate the numerical summary.
    """

    model_config = ConfigDict(extra="forbid")

    score_id: UUID
    candidate_id: UUID
    tenant_id: UUID
    project_id: UUID
    sequence: int
    verification_run_id: UUID | None = None
    score_state: Literal["SCORED", "UNSCORED", "BLOCKED"]
    overall_score: float | None = None
    classification: Literal["GOOD", "MEDIUM", "LOW", "UNSCORED", "BLOCKED"]
    dimensions: dict[str, object]
    hard_failures: list[str]
    evidence_refs: list[str]
    computed_at: datetime
    created_at: datetime
    updated_at: datetime
