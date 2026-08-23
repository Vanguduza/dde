# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SeedDataset(BaseModel):
    """
    Chapter 11.6 versioned seed dataset artifact: content-hashed so an invariant failure
    is reproducible by re-seeding from the same dataset_id + content_hash. Immutable
    after creation (Chapter 3.10: a material change creates a new version, never an
    overwrite).
    """

    model_config = ConfigDict(extra="forbid")

    dataset_id: UUID
    tenant_id: UUID
    project_id: UUID
    slug: str
    version: int
    content_hash: str
    artifact_ref: str
    supersedes_dataset_id: UUID | None = None
    status: Literal["ACTIVE", "SUPERSEDED"]
    created_by: str
    created_at: datetime
