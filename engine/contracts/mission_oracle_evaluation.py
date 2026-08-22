# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MissionOracleEvaluation(BaseModel):
    """
    Chapter 11.3: one evaluation of a mission-scope AcceptanceOracle. Task oracles prove
    the tasks were done; this row proves whether the right product was built. status is
    WRONG_PRODUCT only when every non-retired task oracle has PASSED and the mission
    oracle itself fails -- never fabricated from a missing task oracle (that is
    INCOMPLETE). learning_signal_class is decomposition_quality on WRONG_PRODUCT
    (decomposition quality, not worker quality) and excluded_from_routing_learning is
    true on every row. Owned by engine.verification (Chapter 3.6).
    """

    model_config = ConfigDict(extra="forbid")

    evaluation_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    oracle_id: UUID
    workspace_id: UUID
    status: Literal["ACCEPT", "WRONG_PRODUCT", "INCOMPLETE", "ERRORED"]
    task_oracle_verdict: Literal["all_passed", "incomplete", "task_failed"]
    check_results: list[dict[str, object]]
    outcome_results: list[dict[str, object]]
    recovery_decision: dict[str, object] | None = None
    learning_signal_class: Literal["decomposition_quality", "none"]
    excluded_from_routing_learning: bool
    disclosed_gaps: list[str]
    created_at: datetime
    updated_at: datetime
