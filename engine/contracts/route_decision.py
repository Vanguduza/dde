# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RouteDecision(BaseModel):
    """Immutable routing decision with full candidate recording."""

    model_config = ConfigDict(extra="forbid")

    decision_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID
    candidates: list[dict[str, object]]
    selected_worker_profile_id: str
    workload_class: str
    required_capabilities: list[str]
    required_environment_class: str
    reason_codes: list[str]
    predicted_success: float | None = None
    predicted_cost: float | None = None
    predicted_latency: float | None = None
    confidence: float | None = None
    selection_source: Literal[
        "deterministic",
        "shadow",
        "canary",
        "promoted_historical",
        "exploration",
    ]
    selection_propensity: float
    fallback_plan: list[dict[str, object]]
    escalation_plan: list[dict[str, object]]
    policy_version: str
    decision_hash: str
    created_at: datetime
    updated_at: datetime
