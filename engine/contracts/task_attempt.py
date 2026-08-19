# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TaskAttempt(BaseModel):
    """Durable attempt. WorkerRun is 1:N via worker_runs.task_attempt_id."""

    model_config = ConfigDict(extra="forbid")

    attempt_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID
    sequence: int
    execution_plan_id: UUID
    input_context_hash: str
    workspace_revision: str
    result_artifact_refs: list[UUID]
    verification_refs: list[UUID]
    integration_proposal_id: UUID | None = None
    status: str
    failure_class: str | None = None
    retry_of: UUID | None = None
    checkpoint_id: UUID | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
