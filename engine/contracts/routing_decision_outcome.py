# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RoutingDecisionOutcome(BaseModel):
    """
    Chapter 6.5 real telemetry: 'Even under deterministic routing, DDE records for every
    decision ... actual verified outcome, verification confidence, rework count,
    escalation, human intervention, actual token/tool cost, elapsed time, failure class,
    recovery path, context policy version, capability set, and the attribution from
    Sec5.11.' Decision-time fields (candidate set, predictions, selection_propensity)
    are already durable on the RouteDecision this row references via
    `route_decision_id`; this table stores only the outcome-side signals a RouteDecision
    cannot know about itself, joined back to it. `disclosed_gaps` names Chapter 6.5
    fields this Stage 1 slice cannot populate from a real signal yet (actual token/tool
    cost has no UsageRecord writer in this codebase), never silently defaulted. Owned by
    engine.telemetry (Chapter 3.8).
    """

    model_config = ConfigDict(extra="forbid")

    outcome_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID
    route_decision_id: UUID
    task_attempt_id: UUID
    verification_run_id: UUID
    actual_verified_outcome: Literal["PASSED", "FAILED"]
    verification_confidence: float
    rework_count: int
    escalated: bool
    human_intervention_required: bool
    recovery_action: str | None = None
    failure_class: str | None = None
    elapsed_seconds: float | None = None
    context_package_id: UUID
    capability_set: list[str]
    failure_attribution_id: UUID | None = None
    disclosed_gaps: list[str]
    created_at: datetime
    updated_at: datetime
