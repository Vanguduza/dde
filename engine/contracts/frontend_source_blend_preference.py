# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FrontendSourceBlendPreference(BaseModel):
    """
    DDE-069 durable target source-blend preference for future candidate generation. It
    never rewrites actual provenance; weights are validated by SourceIntelligenceService
    and superseded append-only by scope.
    """

    model_config = ConfigDict(extra="forbid")

    preference_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    scope_key: str
    weights: dict[str, float]
    status: Literal["ACTIVE", "SUPERSEDED"]
    content_hash: str
    created_by: UUID | None = None
    supersedes_id: UUID | None = None
    lock_version: int
    created_at: datetime
    updated_at: datetime
