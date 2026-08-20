# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProductConstitutionVersion(BaseModel):
    """Versioned Product Constitution record. Changes only through change control."""

    model_config = ConfigDict(extra="forbid")

    version_id: UUID
    tenant_id: UUID
    project_id: UUID
    version: int
    status: Literal["draft", "active", "superseded"]
    body_markdown: str
    content_hash: str
    supersedes_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
