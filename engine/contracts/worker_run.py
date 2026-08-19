# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WorkerRun(BaseModel):
    """Worker invocation bound to a TaskAttempt. Cardinality is 1:N."""

    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_attempt_id: UUID
    sequence: int
    execution_plan_id: UUID
    worker_session_id: UUID | None = None
    worker_id: str
    worker_profile_id: str
    environment_id: UUID
    workspace_id: UUID
    context_package_id: UUID
    policy_version: str
    lease_set_hash: str
    checkpoint_id: UUID | None = None
    status: str
    failure_class: str | None = None
    usage_record_id: UUID | None = None
    artifact_manifest_id: UUID | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
