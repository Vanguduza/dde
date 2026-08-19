# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
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
    title: str
    intent: str
    task_class: str
    requirement_refs: list[str]
    feature_refs: list[str]
    success_criteria: list[str]
    expected_write_scope: list[str]
    expected_read_scope: list[str]
    blast_radius: str
    risk_class: str
    estimated_effort: str
    autonomy_ceiling: int
    requires_approval: bool
    verification_profile_ref: str | None = None
    status: str
    lock_version: int
    created_at: datetime
    updated_at: datetime
