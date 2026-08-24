# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ControlPlaneOverheadTask(BaseModel):
    """
    Chapter 16.4 control-plane overhead budget instrumentation: durable per-worker-run
    overhead measurements derived from real production call sites.
    """

    model_config = ConfigDict(extra="forbid")

    overhead_task_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID
    task_attempt_id: UUID
    worker_run_id: UUID
    execution_plan_id: UUID
    context_package_id: UUID
    environment_id: UUID
    estimated_effort: Literal["xs", "s", "m", "l"]
    context_assembly_tokens: int
    context_critic_tokens: int
    overhead_tokens: int
    environment_provisioning_ms: int
    queue_wait_seconds: float
    overhead_seconds_before_first_worker_action_seconds: float
    context_critic_invoked: bool
    created_at: datetime
    updated_at: datetime
