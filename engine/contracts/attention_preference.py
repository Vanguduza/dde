# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AttentionPreference(BaseModel):
    """
    Operator attention budget. Bounds how much non-urgent attention DDE may spend per
    hour and per day, plus quiet hours, repeat cooldown and escalation. Critical
    security and owner-approval events are never suppressed by these budgets.
    """

    model_config = ConfigDict(extra="forbid")

    preference_id: UUID
    tenant_id: UUID
    project_id: UUID
    max_nonurgent_per_hour: int
    max_nonurgent_per_day: int
    quiet_hours: list[dict[str, object]]
    timezone: str
    repeat_cooldown_seconds: int
    escalation_after_seconds: int | None = None
    created_at: datetime
    updated_at: datetime
