# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Outbox(BaseModel):
    """Transactional outbox row committed with authoritative state."""

    model_config = ConfigDict(extra="forbid")

    outbox_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    event_id: UUID
    payload: dict[str, object]
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
