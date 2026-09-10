# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VEKLResearchFinding(BaseModel):
    """
    Typed source-admitted research result. Findings are evidence/candidate intelligence
    and never Project Truth.
    """

    model_config = ConfigDict(extra="forbid")

    finding_id: UUID
    tenant_id: UUID
    project_id: UUID
    unit_map_id: UUID
    task_refs: list[UUID]
    concern: str
    source_id: UUID | None = None
    source_artifact_id: UUID | None = None
    resource_id: UUID | None = None
    source_trust: str
    source_revision: str
    content_hash: str
    claim: str
    supporting_excerpt_hash: str
    freshness: dict[str, object]
    classification: Literal[
        "NORMAL_GUIDANCE",
        "COMPATIBILITY_SIGNAL",
        "SECURITY_SIGNAL",
        "TRUTH_CONFLICT_SIGNAL",
        "DISCOVERY_ONLY",
    ]
    confidence: str
    corroboration_refs: list[str]
    project_truth_refs: list[str]
    stack_refs: list[str]
    impact_hypothesis: list[str]
    created_at: datetime
    updated_at: datetime
