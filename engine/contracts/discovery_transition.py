# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DiscoveryTransition(BaseModel):
    """
    Append-only EDR-0019 Epic C lifecycle history for one DiscoveryCandidate. Rows are
    immutable: deleting, reordering or rewriting a transition is a certification
    failure. sequence is dense and monotonic per candidate. A transition records the
    lifecycle movement only -- it can never carry a source_trust change, because trust
    is not earned by lifecycle progress.
    """

    model_config = ConfigDict(extra="forbid")

    transition_id: UUID
    tenant_id: UUID
    project_id: UUID
    candidate_id: UUID
    sequence: int
    from_state: (
        Literal[
            "DISCOVERED",
            "TRIAGED",
            "PROVENANCE_CHECKED",
            "CONTENT_ACQUIRED",
            "SANITIZED",
            "ARCHITECTURE_CHECKED",
            "TRIAL_ELIGIBLE",
            "SANDBOX_TESTED",
            "QUALIFIED",
            "ADMITTED",
            "REJECTED",
            "SUPERSEDED",
            "REVOKED",
        ]
        | None
    ) = None
    to_state: Literal[
        "DISCOVERED",
        "TRIAGED",
        "PROVENANCE_CHECKED",
        "CONTENT_ACQUIRED",
        "SANITIZED",
        "ARCHITECTURE_CHECKED",
        "TRIAL_ELIGIBLE",
        "SANDBOX_TESTED",
        "QUALIFIED",
        "ADMITTED",
        "REJECTED",
        "SUPERSEDED",
        "REVOKED",
    ]
    reason_code: str
    actor: Literal["SYSTEM", "RESEARCH_MISSION", "OPERATOR", "VERIFIER", "POLICY"]
    evidence_pointer: str | None = None
    decision_hash: str
    occurred_at: datetime
    created_at: datetime
