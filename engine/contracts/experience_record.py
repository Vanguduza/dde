# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ExperienceRecord(BaseModel):
    """
    Chapter 6.8 learning eligibility record. Owned by engine.learning (Chapter 3.8:
    created by the outcome processor; mutable after creation is promotion state only).
    An ExperienceRecord is eligible for routing training only when
    experience_origin=real, verification_confidence is above threshold,
    failure_attribution is route_attributable or none, and the outcome is terminal (no
    in-flight or superseded attempt). Simulation-origin rows are excluded by
    construction (Chapter 6.4) -- eligible_for_routing_training is forced false and a
    table CHECK refuses any other value. promotion_state is the only field a governed
    mutation may change after insert (queue/consume/supersede/block); learning_run_id,
    drift_snapshot_id and promotion_evidence_refs travel with that mutation so DDE-058
    can attach a learner without rewriting observational fields.
    """

    model_config = ConfigDict(extra="forbid")

    experience_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    task_id: UUID | None = None
    route_decision_id: UUID | None = None
    task_attempt_id: UUID | None = None
    verification_run_id: UUID | None = None
    routing_simulation_run_id: UUID | None = None
    outcome_id: UUID | None = None
    experience_origin: Literal["real", "simulation"]
    routing_policy_version: str
    candidate_set_hash: str
    selection_propensity: float
    prediction_vector: dict[str, object]
    observed_outcome_vector: dict[str, object]
    verification_confidence: float
    failure_attribution: Literal[
        "none",
        "route_attributable",
        "context",
        "environment",
        "tool",
        "specification",
        "upstream",
        "inconclusive",
    ]
    attribution_confidence: float
    holdout_partition: Literal["train", "holdout"]
    promotion_evidence_refs: list[UUID]
    drift_snapshot_id: UUID | None = None
    learning_run_id: UUID | None = None
    eligible_for_routing_training: bool
    eligibility_reasons: list[str]
    down_weighted: bool
    promotion_state: Literal[
        "unpromoted",
        "queued_for_learning",
        "consumed",
        "superseded",
        "blocked",
    ]
    created_at: datetime
    updated_at: datetime
