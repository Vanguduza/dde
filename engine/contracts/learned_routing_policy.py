# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LearnedRoutingPolicy(BaseModel):
    """
    Chapter 6.9 frozen full-information routing-policy artifact. Owned by
    engine.learning. The offline phase MUST be a full-information fit over eligible
    recorded decisions before any partial-information update path may exist;
    continued_update is therefore false on every row this mission writes. Mapping is
    immutable after insert; status may move fitted to certified or superseded (Chapter
    3.10: definition immutable, lifecycle mutable). Never a training source from
    simulation (Chapter 6.4).
    """

    model_config = ConfigDict(extra="forbid")

    policy_id: UUID
    tenant_id: UUID
    project_id: UUID
    learning_run_id: UUID
    fit_kind: Literal["frozen_full_information"]
    policy_hash: str
    mapping: dict[str, str]
    constant_policy_profile_id: str
    train_count: int
    holdout_count: int
    brier: float | None = None
    ece: float | None = None
    holdout_learner_expected: float | None = None
    holdout_constant_expected: float | None = None
    holdout_incumbent_success: float | None = None
    beats_constant_policy: bool
    holdout_regression: bool | None = None
    drift_within_bounds: bool | None = None
    continued_update: bool
    status: Literal["fitted", "certified", "superseded"]
    training_experience_ids: list[UUID]
    fallback_robustness_demonstrated: bool
    created_at: datetime
    updated_at: datetime
