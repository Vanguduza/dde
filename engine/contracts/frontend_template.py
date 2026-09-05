# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FrontendTemplate(BaseModel):
    """
    DDE-069 M8 normalized template/foundation recommendation. A template with hard
    failures may be inspected but cannot be locked or promoted into accepted production.
    """

    model_config = ConfigDict(extra="forbid")

    template_id: UUID
    tenant_id: UUID
    project_id: UUID
    source_artifact_id: UUID | None = None
    title: str
    source_refs: list[str]
    supported_archetypes: list[str]
    expected_screen_coverage: float | None = None
    score_summary: dict[str, object]
    hard_failures: list[str]
    status: Literal["RECOMMENDED", "FAVORITED", "LOCKED", "REJECTED", "UNAVAILABLE"]
    content_hash: str | None = None
    created_at: datetime
    updated_at: datetime
