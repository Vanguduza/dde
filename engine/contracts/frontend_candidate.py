# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FrontendCandidate(BaseModel):
    """
    DDE-069 isolated working revision of a project's frontend. Owned by
    engine.studio.candidates (CandidateService is the sole writer). The accepted design
    is never edited in place: even 'editing the current design' mutates a candidate
    based on an accepted revision, and promotion creates the next accepted revision.
    `base_pxg_revision` is what makes staleness detectable -- when the accepted base
    moves past it the candidate is stale and may not promote blindly. `state` is a
    governed lifecycle, not a set of frontend booleans; the transition table lives in
    engine.studio.candidates.lifecycle and a transition outside it is refused.
    """

    model_config = ConfigDict(extra="forbid")

    candidate_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    workspace_id: UUID | None = None
    title: str
    state: Literal[
        "REQUESTED",
        "GENERATING",
        "GENERATED",
        "MATERIALIZING",
        "RENDERING",
        "READY",
        "EDITING",
        "DIRTY",
        "VERIFYING",
        "FAILED",
        "REPAIRABLE",
        "REPAIRING",
        "VERIFIED",
        "REJECTED",
        "BLOCKED",
        "PROMOTABLE",
        "PROMOTING",
        "PROMOTED",
        "SUPERSEDED",
        "ERRORED",
    ]
    origin: Literal[
        "DESIGN_ARTIFACT",
        "DIRECT_EDIT",
        "TEMPLATE_BLEND",
        "SOURCE_IMPORT",
        "AGENT_PACKET",
        "REPAIR_CYCLE",
    ]
    base_pxg_revision: int
    base_contract_version: int | None = None
    scope_keys: list[str]
    verification_run_id: UUID | None = None
    provenance: dict[str, object]
    state_detail: str | None = None
    superseded_by: UUID | None = None
    promoted_at: datetime | None = None
    lock_version: int
    created_at: datetime
    updated_at: datetime
