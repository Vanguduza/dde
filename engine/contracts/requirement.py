# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Requirement(BaseModel):
    """
    Stable, testable statement of intended behaviour with constraints and acceptance
    conditions.
    """

    model_config = ConfigDict(extra="forbid")

    requirement_id: UUID
    tenant_id: UUID
    project_id: UUID
    slug: str
    statement: str
    constraints: list[str]
    acceptance_conditions: list[str]
    status: Literal["draft", "approved", "retired", "superseded"]
    supersedes_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
