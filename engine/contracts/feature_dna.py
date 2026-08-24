# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FeatureDNA(BaseModel):
    """
    Chapter 2.4 / 13.8 Feature DNA - canonical cross-cutting representation of a feature
    extracted from donor material (DDE-046). Stage-5 vertical slice persists a
    deterministic stub body content-hashed as dna_hash; full extraction depth and taint
    propagation into tasks/diffs are DDE-047.
    """

    model_config = ConfigDict(extra="forbid")

    feature_dna_id: UUID
    tenant_id: UUID
    project_id: UUID
    donor_artifact_id: UUID
    title: str
    body: dict[str, object]
    donor_sources: list[str]
    dna_hash: str
    status: Literal["STUB", "COMPLETE"]
    created_at: datetime
    updated_at: datetime
