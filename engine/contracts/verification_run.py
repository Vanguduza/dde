# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VerificationRun(BaseModel):
    """Independent verification run over durable artifacts."""

    model_config = ConfigDict(extra="forbid")

    verification_run_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
