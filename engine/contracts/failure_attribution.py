# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FailureAttribution(BaseModel):
    """
    Chapter 5.11 failure attribution: verification and recovery record whether a FAILED
    VerificationRun was plausibly caused by context omission, contradiction, staleness,
    contamination or mis-ranking. `method` is `rule_based` first; a deterministic rule
    set decides `outcome` from real, already-persisted signals (Chapter 5.8 coverage
    partial/missing, and whether the worker edited outside the task's declared write
    scope). `model_judgment` is the Chapter 5.11 fallback for when the rules are
    inconclusive -- not produced by any writer in this codebase yet (Stage 1 gap,
    disclosed, never silently claimed). `eligible_for_promotion_gating` is true only for
    a rule-derived, non-inconclusive outcome (Chapter 5.11: 'rule-derived attributions
    carry higher confidence and are the only ones eligible to gate policy promotion').
    `excluded_from_routing_learning` is true only when `outcome` is `context_attributed`
    (Chapter 6.8: 'a failure attributed to context must not teach the router that a
    worker is weak'). Owned by engine.attribution (Chapter 3.8).
    """

    model_config = ConfigDict(extra="forbid")

    attribution_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID
    task_attempt_id: UUID
    verification_run_id: UUID
    outcome: Literal["context_attributed", "not_context_attributed", "inconclusive"]
    category: Literal[
        "context_omission",
        "contradiction",
        "staleness",
        "contamination",
        "mis_ranking",
        "none",
    ]
    method: Literal["rule_based", "model_judgment"]
    rule_reasons: list[str]
    confidence: float
    eligible_for_promotion_gating: bool
    excluded_from_routing_learning: bool
    created_at: datetime
    updated_at: datetime
