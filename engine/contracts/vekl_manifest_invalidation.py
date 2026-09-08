# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VEKLManifestInvalidation(BaseModel):
    """
    Append-only invalidation evidence preserving the immutable activation manifest.
    """

    model_config = ConfigDict(extra="forbid")

    invalidation_id: UUID
    tenant_id: UUID
    project_id: UUID
    manifest_id: UUID
    reason_code: str
    detail: dict[str, object]
    observed_policy_hash: str
    observed_truth_hash: str
    created_at: datetime
    updated_at: datetime
