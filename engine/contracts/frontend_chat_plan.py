# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PlanStep(BaseModel):
    """PlanStep nested contract."""

    model_config = ConfigDict(extra="forbid")

    step_id: UUID
    sequence: int
    title: str
    description: str
    state: Literal[
        "PENDING",
        "READY",
        "SUBMITTED",
        "COMPLETED",
        "FAILED",
        "BLOCKED",
        "SKIPPED",
        "CANCELLED",
    ]
    command_type: str | None = None
    target_type: str | None = None
    target_id: UUID | None = None
    parameters: dict[str, object]
    depends_on: list[UUID]
    evidence_refs: list[str]
    command_id: UUID | None = None
    result_summary: str | None = None
    error_code: str | None = None
    error_detail: str | None = None
    idempotency_key: str | None
    expected_request_hash: str | None
    attempt: int


class FrontendChatPlan(BaseModel):
    """
    DDE-069 durable conversational plan. A plan is a proposal until approved; step
    command execution remains a separate normal Gateway command identity.
    """

    model_config = ConfigDict(extra="forbid")

    plan_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    conversation_id: UUID
    title: str
    objective: str
    state: Literal[
        "DRAFT",
        "READY",
        "APPROVED",
        "EXECUTING",
        "PAUSED",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    ]
    approval_required: bool
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    steps: list[PlanStep]
    active_step_id: UUID | None = None
    workspace_id: UUID | None = None
    task_graph_id: UUID | None = None
    created_from_turn_id: UUID | None = None
    context_snapshot: dict[str, object] | None = None
    lock_version: int
    created_at: datetime
    updated_at: datetime
