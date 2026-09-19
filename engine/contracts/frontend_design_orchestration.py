# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FrontendDesignOrchestrationRun(BaseModel):
    """
    EDR-0019 Amendment 1, owner-derived design. Binds the frontend-relevant research
    dimensions (UX, FRONTEND_QUALITY, ACCESSIBILITY) to the existing DDE-069 Frontend
    Studio instead of creating a second design engine. An orchestration run may only
    PROPOSE: the existing frontend candidate, mutation and verification path remains the
    sole authority for applying a change, and visual, silhouette, pixel and
    accessibility verification remain independent verifier duties that this run can
    never satisfy. It holds no design tokens, no golden visual authority and no second
    candidate ledger.
    """

    model_config = ConfigDict(extra="forbid")

    orchestration_id: UUID
    tenant_id: UUID
    project_id: UUID
    research_packet_id: UUID | None = None
    design_session_id: UUID | None = None
    frontend_contract_ref: str | None = None
    screen_refs: list[str]
    guidance_dimensions: list[Literal["UX", "FRONTEND_QUALITY", "ACCESSIBILITY"]]
    guidance_findings: list[dict[str, object]]
    proposed_candidate_refs: list[str]
    applied_mutation_refs: list[str]
    state: Literal[
        "PREPARED",
        "GUIDANCE_COMPILED",
        "CANDIDATES_PROPOSED",
        "OPERATOR_REVIEW",
        "APPLIED",
        "REJECTED",
        "SUPERSEDED",
    ]
    authority: Literal["ADVISORY"]
    verification_satisfied: bool
    rejected_reason: str | None = None
    created_at: datetime
    updated_at: datetime
