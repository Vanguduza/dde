# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SteeringImpact(BaseModel):
    """
    The computed consequence of one steer on one task, including the steering hold. The
    hold lives here rather than in task.status: the core task state machine is not
    widened by this programme, and the scheduler consults open impacts when deciding
    eligibility. Holds are released explicitly, so a crashed steer cannot strand a task
    in a hidden state.
    """

    model_config = ConfigDict(extra="forbid")

    impact_id: UUID
    tenant_id: UUID
    project_id: UUID
    steer_id: UUID
    task_id: UUID
    impact_kind: Literal[
        "HELD",
        "SUPERSEDED",
        "REPLANNED",
        "LEASE_CLOSED",
        "CONTEXT_RECOMPILE_REQUIRED",
        "UNAFFECTED",
    ]
    hold_state: Literal["NONE", "STEERING_HELD", "RELEASED"]
    previous_task_status: str | None = None
    closed_lease_refs: list[str]
    reason_code: str
    held_at: datetime | None = None
    released_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
