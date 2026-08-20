# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Edr(BaseModel):
    """Engineering Decision Record. Accepted records are superseded, never rewritten."""

    model_config = ConfigDict(extra="forbid")

    edr_id: UUID
    tenant_id: UUID
    project_id: UUID
    slug: str
    context: str
    alternatives: list[str]
    decision: str
    rationale: str
    consequences: list[str]
    affected_requirement_slugs: list[str]
    status: Literal["proposed", "accepted", "rejected", "superseded"]
    supersedes_id: UUID | None = None
    decided_by_principal: UUID | None = None
    decided_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
