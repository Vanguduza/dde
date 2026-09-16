# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AutomationWorkflowArtifact(BaseModel):
    """
    Quarantined raw n8n workflow member of an exact corpus snapshot. Raw content never
    enters worker context.
    """

    model_config = ConfigDict(extra="forbid")

    workflow_artifact_id: UUID
    tenant_id: UUID
    project_id: UUID
    snapshot_id: UUID
    artifact_id: UUID
    path: str
    raw_hash: str
    raw_size_bytes: int
    parser_state: str
    source_metadata: dict[str, object]
    state: Literal["QUARANTINED", "SANITIZED", "REJECTED", "BLOCKED"]
    findings: list[str]
    pattern_lineage_id: str | None = None
    created_at: datetime
    updated_at: datetime
