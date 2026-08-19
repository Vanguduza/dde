# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Evidence(BaseModel):
    """Append-only verification evidence bound to an integrated revision."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID
    verification_run_id: UUID
    integrated_revision: str
    oracle_id: UUID | None = None
    outcome_id: UUID | None = None
    evidence_type: str
    artifact_refs: list[UUID]
    content_hash: str
    signature: str
    produced_by: str
    independence_flags: dict[str, object]
    recorded_at: datetime
    status: str
    created_at: datetime
    updated_at: datetime
