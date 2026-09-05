# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ScreenAuditEvidence(BaseModel):
    """
    Reference-oriented evidence for one Screen Audit fact. Existing
    VerificationRun/PXG/Contract/source evidence is referenced instead of copied as new
    truth.
    """

    model_config = ConfigDict(extra="forbid")

    evidence_id: UUID
    audit_run_id: UUID
    finding_id: UUID | None = None
    tenant_id: UUID
    project_id: UUID
    pxg_key: str | None = None
    dimension: Literal[
        "CONTRACT",
        "JOURNEY",
        "FUNCTIONAL",
        "STATE",
        "DATA",
        "ROLE",
        "PERMISSION",
        "NAVIGATION",
        "ACCESSIBILITY",
        "RESPONSIVE_PLATFORM",
        "VISUAL",
        "SOURCE_PROVENANCE",
        "SECURITY",
        "VERIFICATION",
        "DRIFT",
    ]
    evidence_kind: str
    source_type: str
    source_ref: str
    source_revision: str | None = None
    content_hash: str | None = None
    assessment_state: Literal[
        "PASS",
        "FAIL",
        "PARTIAL",
        "UNKNOWN",
        "BLOCKED",
        "NOT_APPLICABLE",
    ]
    metadata: dict[str, object]
    stale: bool
    observed_at: datetime
    created_at: datetime
    updated_at: datetime
