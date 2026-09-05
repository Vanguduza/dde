# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RoutingInsightCandidate(BaseModel):
    """
    Hermes/evaluator routing insight candidate. Never mutates routing policy directly.
    """

    model_config = ConfigDict(extra="forbid")

    insight_id: UUID
    tenant_id: UUID
    project_id: UUID
    source_kind: Literal["HERMES", "EVALUATOR", "HUMAN", "OTHER"]
    source_ref: str
    proposal: dict[str, object]
    evidence_refs: list[str]
    confidence: float
    state: Literal[
        "CANDIDATE",
        "OFFLINE_REPLAY",
        "HOLDOUT",
        "SHADOW",
        "CANARY",
        "PROMOTED",
        "REJECTED",
        "SUPERSEDED",
    ]
    evaluation_refs: list[str]
    promoted_policy_ref: str | None = None
    promoted_by: UUID | None = None
    promoted_at: datetime | None = None
    lock_version: int
    created_at: datetime
    updated_at: datetime
