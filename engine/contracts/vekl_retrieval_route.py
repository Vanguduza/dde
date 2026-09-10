# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VEKLRetrievalRoute(BaseModel):
    """
    Versioned deterministic GraphRAG route policy. It selects graph relations and
    ranking semantics, never raw internet queries.
    """

    model_config = ConfigDict(extra="forbid")

    route_id: UUID
    tenant_id: UUID
    project_id: UUID
    route_slug: str
    version: str
    concern: str
    policy: dict[str, object]
    policy_hash: str
    active: bool
    created_at: datetime
    updated_at: datetime
