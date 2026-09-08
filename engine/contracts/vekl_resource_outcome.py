# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VEKLResourceOutcome(BaseModel):
    """
    Verifier-backed VEKL resource effectiveness record, distinct from ExperienceRecord
    and ExecutionExperienceRecord.
    """

    model_config = ConfigDict(extra="forbid")

    outcome_id: UUID
    tenant_id: UUID
    project_id: UUID
    manifest_id: UUID
    resource_revisions: list[dict[str, object]]
    verifier_refs: list[str]
    verified_outcome: Literal["PASS", "FAIL", "PARTIAL"]
    regressions: list[str]
    iterations: int
    rework: dict[str, object]
    cost: dict[str, object]
    latency_ms: int
    failure_signatures: list[str]
    evidence_refs: list[str]
    recorded_by: Literal["DDE_VERIFIER", "DDE_OPERATOR"]
    created_at: datetime
    updated_at: datetime
