# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MissionControl(BaseModel):
    """
    Operational projection for GET /v1/mission-control/{id} (Chapter 15.4). Aggregates
    mission status, task progress, the attention model (Chapter 13.4) and autonomy-
    economics metrics (Chapter 16) from durable rows. A read model, never a second
    source of truth. last_event_at is the reconnect cursor a client replays from
    (Chapter 15.1).
    """

    model_config = ConfigDict(extra="forbid")

    mission_id: UUID
    tenant_id: UUID
    project_id: UUID
    slug: str
    title: str
    status: Literal[
        "CREATED",
        "ACTIVE",
        "PARTIAL",
        "PAUSED",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    ]
    autonomy_ceiling: int
    lock_version: int
    task_total: int
    task_counts: dict[str, int]
    tasks_completed: int
    open_attention_items: int
    attention_debt: int
    human_minutes: float
    approvals_per_mission: int
    approvals_by_type: dict[str, int]
    blocked_requests: int
    standing_approval_usage: int
    last_event_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
