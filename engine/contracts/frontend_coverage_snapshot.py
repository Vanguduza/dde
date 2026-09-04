# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DimensionResult(BaseModel):
    """DimensionResult nested contract."""

    model_config = ConfigDict(extra="forbid")

    dimension: str
    state: Literal["UNASSESSED", "PARTIAL", "ASSESSED", "BLOCKED"]
    required_count: int
    satisfied_count: int
    missing_count: int
    unverified_count: int
    blocked_count: int
    waived_count: int
    percent: float | None = None


class Finding(BaseModel):
    """Finding nested contract."""

    model_config = ConfigDict(extra="forbid")

    finding_kind: Literal[
        "MISSING",
        "UNVERIFIED",
        "BLOCKED",
        "WAIVED",
        "THIN_SCREEN",
        "ORPHAN_NODE",
        "DANGLING_EDGE",
    ]
    dimension: str
    pxg_key: str
    obligation_id: UUID | None = None
    detail: str


class FrontendCoverageSnapshot(BaseModel):
    """
    DDE-069 computed comparison of a FrontendContract against the Project Experience
    Graph at a pinned revision. Owned by engine.studio.coverage (CoverageService is the
    sole writer). The golden UI's coverage ring reads `weighted_percent` from here and
    nowhere else. That field is deliberately nullable: it is populated only when every
    dimension is fully ASSESSED, so an unassessed or blocked project shows an explicit
    em-dash rather than a number that reads as certainty. MISSING, BLOCKED, WAIVED and
    UNVERIFIED are kept as separate counts throughout, because 'we did not check' and
    'we checked and it failed' are different facts and collapsing them is the exact
    dishonesty this snapshot exists to prevent.
    """

    model_config = ConfigDict(extra="forbid")

    snapshot_id: UUID
    tenant_id: UUID
    project_id: UUID
    contract_id: UUID
    contract_version: int
    pxg_revision: int
    summary_state: Literal["UNASSESSED", "PARTIAL", "ASSESSED", "BLOCKED"]
    weighted_percent: float | None = None
    dimensions: list[DimensionResult]
    findings: list[Finding]
    created_at: datetime
    updated_at: datetime
