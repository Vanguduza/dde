# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FeatureDNA(BaseModel):
    """
    Chapter 2.4 / 13.8 Feature DNA - canonical cross-cutting representation of a feature
    extracted from donor material (DDE-046/047). dna_hash content-addresses the body;
    taint_tags answer which donor evidence influenced this DNA (propagated further via
    donor_taints).
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
    taint_tags: list[str]
    status: Literal["STUB", "COMPLETE"]
    created_at: datetime
    updated_at: datetime
