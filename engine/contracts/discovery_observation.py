# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DiscoveryObservation(BaseModel):
    """
    One evidence sighting of a DiscoveryCandidate. Independent discoveries of the same
    normalized identity append observations rather than creating duplicate candidates.
    Observation content is untrusted external material and may never alter task
    authority, policy or Project Truth.
    """

    model_config = ConfigDict(extra="forbid")

    observation_id: UUID
    tenant_id: UUID
    project_id: UUID
    candidate_id: UUID
    observed_via: Literal[
        "RESEARCH_PROVIDER",
        "SOURCE_FEED",
        "OPERATOR_SUBMISSION",
        "CORROBORATION",
        "REGISTRY",
    ]
    observer_ref: str | None = None
    claim_excerpt_hash: str | None = None
    content_hash: str | None = None
    corroborates_observation_id: UUID | None = None
    observed_at: datetime
    created_at: datetime
