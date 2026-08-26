# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ContextActivationState(BaseModel):
    """
    Chapter 5.13 durable context-policy mode per tenant/project (DDE-059). Owned by
    engine.context. The sole writers are ContextActivationService.attempt_advance
    (forward one step after gates) and ContextActivationService.rollback (return to last
    certified policy, never an untested arm). ContextService.compile() is the production
    reader: certified_baseline and shadow serve the Stage 1 pull policy with semantic
    retrieval off; canary applies the candidate arm on a limited hash-stable slice;
    promoted applies the candidate arm to all compiles.
    PARTIAL_PASS_IMPLEMENTED_GATES_ONLY never advances canary or promoted. One row per
    (tenant_id, project_id).
    """

    model_config = ConfigDict(extra="forbid")

    activation_id: UUID
    tenant_id: UUID
    project_id: UUID
    context_mode: Literal["certified_baseline", "shadow", "canary", "promoted"]
    candidate_arm: Literal["pull", "push", "semantic"]
    last_certified_mode: Literal["certified_baseline", "shadow", "canary", "promoted"]
    last_certified_arm: Literal["pull", "push", "semantic"]
    last_promotion_run_id: UUID | None = None
    canary_fraction: float
    created_at: datetime
    updated_at: datetime
