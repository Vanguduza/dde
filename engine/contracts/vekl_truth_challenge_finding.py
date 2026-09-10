# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VEKLTruthChallengeFinding(BaseModel):
    """Project-scoped join binding a Truth Challenge to its exact research findings."""

    model_config = ConfigDict(extra="forbid")

    challenge_finding_id: UUID
    tenant_id: UUID
    project_id: UUID
    challenge_id: UUID
    finding_id: UUID
    created_at: datetime
    updated_at: datetime
