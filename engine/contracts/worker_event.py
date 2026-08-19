# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WorkerEvent(BaseModel):
    """
    Append-only worker lifecycle event. Partitioned by occurred_at per Chapter 3.7.
    """

    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    run_id: UUID
    task_id: UUID
    sequence: int
    event_type: str
    occurred_at: datetime
    actor: str
    correlation_id: str
    causation_id: str | None = None
    payload: dict[str, object]
    schema_version: str
    integrity_hash: str
    created_at: datetime
    updated_at: datetime
