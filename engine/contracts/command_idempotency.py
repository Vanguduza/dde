# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CommandIdempotency(BaseModel):
    """
    Command ledger. expires_at must exceed max retry, reconnect and pause windows
    (Chapter 3.7).
    """

    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    tenant_id: UUID
    project_id: UUID
    idempotency_key: str
    request_hash: str
    status: str
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
