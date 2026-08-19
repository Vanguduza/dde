# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Artifact(BaseModel):
    """Artifact metadata. Bytes live in object storage, content-addressed by SHA-256."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    task_id: UUID | None = None
    content_hash: str
    storage_key: str
    created_at: datetime
    updated_at: datetime
