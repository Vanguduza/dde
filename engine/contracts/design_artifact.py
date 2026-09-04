# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DesignArtifact(BaseModel):
    """
    DDE-069 one versioned design direction produced by a design provider. Owned by
    engine.studio.design. An artifact is *not* an implementation and is never LIVE: it
    becomes code only through Try live, which creates an isolated candidate, and it
    reaches accepted state only through the ordinary promotion gate with DDE-068
    verification. `provenance` records the provider, its version, the request and the
    design-system hash, so "where did this come from?" is answerable after the fact.
    Artifacts are neutral directions -- a card may not imply a quality score before real
    scoring evidence exists (FRONTEND_STUDIO_REV3 section 17.2).
    """

    model_config = ConfigDict(extra="forbid")

    artifact_id: UUID
    tenant_id: UUID
    project_id: UUID
    session_id: UUID
    direction_label: str
    revision: int
    status: Literal["GENERATED", "QUARANTINED", "SELECTED", "TRIED_LIVE", "DISCARDED"]
    provider_id: str
    content_hash: str
    content: dict[str, object]
    provenance: dict[str, object]
    quarantine_reason: str | None = None
    candidate_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
