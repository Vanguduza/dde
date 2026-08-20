# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditEvent(BaseModel):
    """Hash-chained audit ledger. Never detached."""

    model_config = ConfigDict(extra="forbid")

    audit_event_id: UUID
    tenant_id: UUID
    project_id: UUID | None = None
    event_type: str
    sequence: int
    prev_hash: str | None = None
    entry_hash: str
    payload: dict[str, object]
    created_at: datetime
    updated_at: datetime
