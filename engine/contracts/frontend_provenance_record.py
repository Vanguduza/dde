# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FrontendProvenanceRecord(BaseModel):
    """
    DDE-069 M8 append-only source attribution for PXG nodes, candidates, templates and
    components. Actual attribution is evidence, never rewritten by target blend
    preferences.
    """

    model_config = ConfigDict(extra="forbid")

    provenance_id: UUID
    tenant_id: UUID
    project_id: UUID
    subject_kind: Literal[
        "PXG_NODE",
        "CANDIDATE",
        "TEMPLATE",
        "COMPONENT",
        "DESIGN_ARTIFACT",
    ]
    subject_ref: str
    source_id: UUID | None = None
    artifact_id: UUID | None = None
    admission_id: UUID | None = None
    usage_kind: Literal["REUSED", "ADAPTED", "INSPIRED", "REFERENCE", "GENERATED"]
    attribution_weight: float | None = None
    source_revision: str | None = None
    license_state: str
    security_state: str
    decision_ref: str | None = None
    metadata: dict[str, object]
    created_at: datetime
    updated_at: datetime
