# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FrontendPreviewScenario(BaseModel):
    """
    DDE-069 explicit simulated product state for one preview session. This is distinct
    from PreviewState, which attests browser/runtime lifecycle. Scenario selection never
    claims the preview itself is loading/error/offline.
    """

    model_config = ConfigDict(extra="forbid")

    scenario_id: UUID
    tenant_id: UUID
    project_id: UUID
    preview_session_id: UUID
    scenario: Literal["DEFAULT", "LOADING", "EMPTY", "ERROR", "OFFLINE", "ROLE"]
    role: str | None = None
    updated_by: UUID
    lock_version: int
    created_at: datetime
    updated_at: datetime
