# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RoutingActivationState(BaseModel):
    """
    Chapter 6.9 durable routing.mode per tenant/project. Owned by engine.learning; the
    sole writers are LearningActivationService.attempt_advance (forward one step after
    gates) and LearningActivationService.rollback (return to last certified policy,
    never an untested fallback). RouterService.route() is the production reader that
    applies frozen exploitation on the canary slice or promoted_historical traffic. One
    row per (tenant_id, project_id).
    """

    model_config = ConfigDict(extra="forbid")

    activation_id: UUID
    tenant_id: UUID
    project_id: UUID
    routing_mode: Literal[
        "deterministic",
        "shadow_learning",
        "canary",
        "promoted_historical",
    ]
    active_policy_id: UUID | None = None
    last_certified_policy_id: UUID | None = None
    last_certified_mode: Literal[
        "deterministic",
        "shadow_learning",
        "canary",
        "promoted_historical",
    ]
    canary_fraction: float
    continued_update_enabled: bool
    created_at: datetime
    updated_at: datetime
