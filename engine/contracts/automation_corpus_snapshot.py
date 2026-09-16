# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AutomationCorpusSnapshot(BaseModel):
    """
    Exact-pinned quarantined public workflow-corpus snapshot admitted under EDR-0018.
    """

    model_config = ConfigDict(extra="forbid")

    snapshot_id: UUID
    tenant_id: UUID
    project_id: UUID
    source_id: UUID
    artifact_id: UUID
    repository: str
    commit_sha: str
    archive_sha256: str
    acquisition_policy_version: str
    acquisition_policy_hash: str
    acquisition_effect_id: UUID
    acquired_at: datetime
    compressed_bytes: int
    expanded_bytes: int
    workflow_count: int
    object_ref: str
    object_backend: str
    state: Literal["QUARANTINED", "ADMITTED", "REJECTED", "REVOKED"]
    license_state: Literal["VERIFIED", "REJECTED"]
    license_path: str | None = None
    created_at: datetime
    updated_at: datetime
