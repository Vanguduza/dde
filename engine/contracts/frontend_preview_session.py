# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FrontendPreviewSession(BaseModel):
    """
    DDE-069 code-backed candidate preview session. Owned by engine.studio.preview. A
    LIVE session proves an isolated candidate workspace exists, a preview document was
    materialised from that workspace, the browser loaded the exact content hash, and the
    candidate/accepted revisions still match. Design artifacts and screenshots cannot
    create LIVE sessions.
    """

    model_config = ConfigDict(extra="forbid")

    preview_session_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    candidate_id: UUID
    workspace_id: UUID | None = None
    screen_key: str
    state: Literal[
        "BUILDING",
        "LOADING",
        "LIVE",
        "STALE",
        "RUNTIME_ERROR",
        "RENDER_ERROR",
        "UNAVAILABLE",
        "STOPPED",
    ]
    viewport: str
    route: str | None = None
    candidate_pxg_revision: int
    source_revision: str | None = None
    document_path: str | None = None
    content_hash: str | None = None
    state_detail: str | None = None
    lock_version: int
    created_at: datetime
    updated_at: datetime
    source_path: str | None = None
