# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AiClaim(BaseModel):
    """
    Per-turn epistemic annotation distinguishing fact/source/inference/proposal/unknown.
    """

    model_config = ConfigDict(extra="forbid")

    claim_id: UUID
    tenant_id: UUID
    project_id: UUID
    conversation_id: UUID
    turn_id: UUID
    claim_text: str
    epistemic_class: Literal[
        "REPOSITORY_FACT",
        "EXTERNAL_SOURCE",
        "INFERENCE",
        "PROPOSAL",
        "UNKNOWN",
    ]
    confidence: float | None = None
    source_refs: list[str]
    verification_state: Literal["UNVERIFIED", "SUPPORTED", "CONTRADICTED", "SUPERSEDED"]
    created_at: datetime
    updated_at: datetime
