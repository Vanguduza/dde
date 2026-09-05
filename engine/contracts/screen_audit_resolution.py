# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ScreenAuditResolution(BaseModel):
    """
    Durable authority explaining how a ScreenAuditFinding left an unresolved state.
    Chat/model assertions are not valid resolution kinds.
    """

    model_config = ConfigDict(extra="forbid")

    resolution_id: UUID
    finding_id: UUID
    tenant_id: UUID
    project_id: UUID
    resolution_kind: Literal[
        "PROMOTED_REVISION",
        "ACCEPTED_EXCEPTION",
        "REQUIREMENT_SUPERSEDED",
        "SOURCE_CORRECTION",
    ]
    candidate_id: UUID | None = None
    accepted_revision: str | None = None
    decision_ref: str | None = None
    evidence_refs: list[UUID]
    resolved_by: UUID | None = None
    resolved_at: datetime
    created_at: datetime
    updated_at: datetime
