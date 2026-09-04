# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Obligation(BaseModel):
    """Obligation nested contract."""

    model_config = ConfigDict(extra="forbid")

    obligation_id: UUID
    dimension: Literal[
        "screen",
        "journey",
        "component",
        "interaction",
        "state",
        "data_state",
        "responsive",
        "accessibility",
        "navigation",
        "verification",
    ]
    pxg_key: str
    statement: str
    requirement_refs: list[str]
    applicability: Literal[
        "REQUIRED",
        "OPTIONAL_SELECTED",
        "DEFERRED_APPROVED",
        "NOT_APPLICABLE_APPROVED",
        "BLOCKED_RECORDED",
    ]
    applicability_decision_ref: str | None = None
    verification_kinds: list[
        Literal[
            "test",
            "db_assertion",
            "api_probe",
            "visual_diff",
            "silhouette",
            "visual_critique",
            "security_scan",
            "android_scan",
            "invariant",
            "judge",
            "human",
        ]
    ]


class FrontendContract(BaseModel):
    """
    DDE-069 declarative statement of what a project's frontend is obliged to contain,
    independent of what it currently renders. Owned by engine.studio.contract
    (FrontendContractService is the sole writer). This is the 'complete according to
    product intent' half of the pair whose other half is the Project Experience Graph
    ('what actually exists'); CoverageService compares them. Every obligation carries an
    explicit applicability, so an omission is always a recorded decision and never
    silence (FRONTEND_STUDIO_REV3 section 13.1: 'There is no silent omission state').
    Immutable per version: a change publishes a new contract_version for the same
    project and supersedes the previous row, so a coverage snapshot can always be
    replayed against the exact contract it was computed from.
    """

    model_config = ConfigDict(extra="forbid")

    contract_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    contract_version: int
    content_hash: str
    status: Literal["DRAFT", "ACTIVE", "SUPERSEDED"]
    obligations: list[Obligation]
    created_at: datetime
    updated_at: datetime
