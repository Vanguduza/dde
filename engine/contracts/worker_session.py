# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WorkerSession(BaseModel):
    """
    Blueprint §9 durable long-lived harness/session lineage; WorkerRun remains one
    bounded attempt.
    """

    model_config = ConfigDict(extra="forbid")

    worker_session_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    task_id: UUID | None = None
    endpoint_id: UUID
    worker_profile_id: str | None = None
    provider_session_ref: str | None = None
    requested_model_id: str | None = None
    serving_model_id: str | None = None
    workspace_id: UUID | None = None
    state: Literal[
        "OPENING",
        "ACTIVE",
        "PAUSED",
        "DETACHED",
        "RESUMING",
        "FAILED",
        "CLOSED",
    ]
    capability_snapshot: dict[str, object]
    context_package_hash: str | None = None
    tool_policy_hash: str | None = None
    session_config_hash: str
    parent_session_id: UUID | None = None
    forked_from_session_id: UUID | None = None
    last_error: str | None = None
    lock_version: int
    created_at: datetime
    last_activity_at: datetime
    updated_at: datetime
