# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class StackFingerprint(BaseModel):
    """
    Deterministic target-project stack facts derived from Project Truth and observed
    repository/runtime evidence; never model-guessed.
    """

    model_config = ConfigDict(extra="forbid")

    fingerprint_id: UUID
    tenant_id: UUID
    project_id: UUID
    project_truth_hash: str
    facts: dict[str, object]
    evidence_refs: list[str]
    fingerprint_hash: str
    created_at: datetime
    updated_at: datetime
