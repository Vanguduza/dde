# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Task(BaseModel):
    """
    Materialised TaskGraph node with lifecycle state. Optimistic locking required by
    Chapter 3.5.
    """

    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    graph_id: UUID
    parent_task_id: UUID | None = None
    title: str
    intent: str
    task_class: Literal[
        "discovery",
        "specification",
        "decision",
        "enabling",
        "implementation",
        "integration",
        "verification",
        "repair",
        "documentation",
    ]
    requirement_refs: list[str]
    feature_refs: list[str]
    success_criteria: list[str]
    expected_write_scope: list[str]
    expected_read_scope: list[str]
    blast_radius: Literal["none", "local", "module", "cross_module", "systemic"]
    risk_class: Literal["low", "medium", "high", "critical"]
    estimated_effort: Literal["xs", "s", "m", "l"]
    autonomy_ceiling: int
    requires_approval: bool
    verification_profile_ref: str | None = None
    status: Literal[
        "CREATED",
        "BLOCKED",
        "READY",
        "CONTEXT_READY",
        "ROUTED",
        "PLANNED",
        "EXECUTING",
        "VERIFYING",
        "INTEGRATING",
        "COMPLETED",
        "REPAIR_REQUIRED",
        "MERGE_CONFLICT",
        "RETRYING",
        "REROUTING",
        "BLOCKED_ON_DECISION",
        "SUPERSEDED",
        "RETIRED",
    ]
    lock_version: int
    created_at: datetime
    updated_at: datetime
