# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VEKLConflictObservation(BaseModel):
    """
    Execution-rejected Project Truth conflict eligible for governed challenge
    evaluation; never worker implementation guidance.
    """

    model_config = ConfigDict(extra="forbid")

    observation_id: UUID
    tenant_id: UUID
    project_id: UUID
    resource_id: UUID
    finding_id: UUID
    current_truth_hash: str
    conflicting_truth_refs: list[str]
    conflict_keys: list[str]
    source_trust: str
    freshness: dict[str, object]
    provenance_valid: bool
    activation_rejected: bool
    challenge_evaluation_requested: bool
    created_at: datetime
    updated_at: datetime
