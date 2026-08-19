# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CoreEvent(BaseModel):
    """Event envelope from Chapter 15.2. Payload is versioned per event type."""

    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    task_id: UUID | None = None
    sequence: int
    occurred_at: datetime
    correlation_id: str
    causation_id: str | None = None
    payload: dict[str, object]
    schema_version: str
