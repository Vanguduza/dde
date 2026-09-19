# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ExternalEffectVerification(BaseModel):
    """
    EDR-0019 Epic F independent postcondition observation for one ExternalEffect. 'The
    API accepted the request' is not 'the desired state exists'. This contract is
    additive: external_effects.status keeps its existing
    PREPARED/SENT/CONFIRMED/FAILED/UNKNOWN/RECONCILING/RECONCILED transport-and-recovery
    meaning, and the separate external_effects.postcondition_state axis is driven by
    these observations. For high-impact effect classes a VERIFIED postcondition requires
    an observation produced independently of the adapter that performed the effect.
    """

    model_config = ConfigDict(extra="forbid")

    verification_id: UUID
    tenant_id: UUID
    project_id: UUID
    effect_id: UUID
    verifier_type: Literal[
        "API_READBACK",
        "STATE_QUERY",
        "FILE_HASH",
        "BROWSER_OBSERVATION",
        "DATABASE_READBACK",
        "CUSTOM",
    ]
    independent_of_adapter: bool
    observed_postcondition: str
    outcome: Literal["SUCCESS", "PARTIAL", "REFUTED", "UNVERIFIABLE", "ERROR"]
    correlation: str | None = None
    evidence_pointer: str | None = None
    observation_hash: str
    observed_at: datetime
    created_at: datetime
