# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FrontendPreviewSession(BaseModel):
    """
    A durable DDE-069 code-backed candidate preview. Owned by engine.studio.preview.
    READY means the candidate graph was materialized into an isolated Workspace
    artifact, its content hash was recorded, and that exact artifact can be served to
    the Frontend Studio canvas. A design image or stale render can never satisfy READY.
    """

    model_config = ConfigDict(extra="forbid")

    preview_session_id: UUID
    tenant_id: UUID
    project_id: UUID
    candidate_id: UUID
    workspace_id: UUID
    status: Literal[
        "BUILDING",
        "LOADING",
        "READY",
        "RUNTIME_ERROR",
        "RENDER_ERROR",
        "STALE",
        "UNAVAILABLE",
        "STOPPED",
    ]
    candidate_pxg_revision: int
    route_key: str
    document_path: str
    document_sha256: str
    selected_pxg_key: str | None = None
    error_code: str | None = None
    error_detail: str | None = None
    built_at: datetime | None = None
    lock_version: int
    created_at: datetime
    updated_at: datetime
