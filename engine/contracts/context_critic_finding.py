# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ContextCriticFinding(BaseModel):
    """
    Chapter 5.9 Context Critic record. Written whenever the triggered-not-default critic
    fires during ContextService.compile() -- `trigger_reasons` names which of Chapter
    5.9's five trigger conditions held. The critic may only request additional retrieval
    (`action=requested_additional_retrieval`, recovering already-fused evidence the
    Chapter 5.7 eviction pass dropped) or raise a finding (`action=raised_finding`) when
    it cannot; it can never alter Project Truth and can never approve its own request,
    so `requires_human_review` is true whenever a raised finding still leaves a required
    category unresolved, and `reviewed`/`reviewed_at` are the observable state of that
    outstanding review. `cost_tokens_estimate` counts the critic pass against the
    Chapter 16.4 control-plane overhead budget. Owned by engine.context (Chapter 3.8,
    alongside ContextPackage).
    """

    model_config = ConfigDict(extra="forbid")

    finding_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID
    package_id: UUID
    trigger_reasons: list[str]
    confidence: float
    action: Literal["requested_additional_retrieval", "raised_finding"]
    outcome_summary: str
    requires_human_review: bool
    reviewed: bool
    reviewed_at: datetime | None = None
    cost_tokens_estimate: int
    created_at: datetime
    updated_at: datetime
