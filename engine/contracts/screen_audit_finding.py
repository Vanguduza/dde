# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ScreenAuditFinding(BaseModel):
    """
    Durable typed Screen Audit finding. Resolution is evidence-driven and records are
    never deleted to simulate success.
    """

    model_config = ConfigDict(extra="forbid")

    finding_id: UUID
    audit_run_id: UUID
    tenant_id: UUID
    project_id: UUID
    pxg_key: str | None = None
    node_key: str | None = None
    finding_type: str
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
    severity: Literal["BLOCKING", "ERROR", "WARNING", "INFO"]
    status: Literal[
        "DETECTED",
        "CONFIRMED",
        "CANDIDATE_CREATED",
        "ASSIGNED",
        "VERIFYING",
        "RESOLVED",
        "ACCEPTED_EXCEPTION",
        "BLOCKED",
        "SUPERSEDED",
    ]
    assessment_state: Literal[
        "PASS",
        "FAIL",
        "PARTIAL",
        "UNKNOWN",
        "BLOCKED",
        "NOT_APPLICABLE",
    ]
    message: str
    evidence_refs: list[UUID]
    requirement_refs: list[str]
    journey_refs: list[str]
    role_refs: list[str]
    dependency_keys: list[str]
    rule_id: str
    rule_version: str
    first_detected_at: datetime
    last_observed_at: datetime
    resolved_at: datetime | None = None
    resolution_ref: UUID | None = None
    decision_ref: str | None = None
    stale: bool
    lock_version: int
    created_at: datetime
    updated_at: datetime
