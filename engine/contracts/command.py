# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Command(BaseModel):
    """Command envelope from Chapter 15.2."""

    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    idempotency_key: str
    principal_id: UUID
    client_session_id: UUID | None = None
    target_type: str
    target_id: UUID
    command_type: str
    parameters: dict[str, object]
    requested_at: datetime
    protocol_version: str
