# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TaskAttempt(BaseModel):
    """
    Durable attempt (Chapter 12.2). WorkerRun is 1:N via worker_runs.task_attempt_id.
    Result, artifact refs and state are committed on the same row (Attempt commit); a
    retry is a new row (retry_of), which is what Chapter 3.8's Append-only note means.
    status is IN_PROGRESS | COMPLETED | FAILED. COMPLETED is written only after
    verification (Chapter 3.9 step 15). A COMPLETED attempt is never re-run because a
    later task failed.
    """

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
    status: Literal["IN_PROGRESS", "COMPLETED", "FAILED"]
    failure_class: str | None = None
    retry_of: UUID | None = None
    checkpoint_id: UUID | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
