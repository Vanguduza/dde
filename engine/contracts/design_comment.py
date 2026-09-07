# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DesignComment(BaseModel):
    """
    DDE-069 anchored design review comment. Comments are project-scoped review records
    anchored to a PXG key and optionally an isolated candidate. Resolution is explicit
    and auditable; losing the anchor never silently deletes the comment.
    """

    model_config = ConfigDict(extra="forbid")

    comment_id: UUID
    tenant_id: UUID
    project_id: UUID
    candidate_id: UUID | None = None
    pxg_key: str
    body: str
    status: Literal["OPEN", "RESOLVED"]
    created_by: UUID
    resolved_by: UUID | None = None
    resolved_at: datetime | None = None
    lock_version: int
    created_at: datetime
    updated_at: datetime
