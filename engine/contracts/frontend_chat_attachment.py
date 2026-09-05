# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FrontendChatAttachment(BaseModel):
    """
    DDE-069 managed Chat attachment metadata. Bytes are content-addressed in scoped
    managed storage; attachment text is context, never executable instruction.
    """

    model_config = ConfigDict(extra="forbid")

    attachment_id: UUID
    tenant_id: UUID
    project_id: UUID
    conversation_id: UUID
    turn_id: UUID | None = None
    source_kind: Literal["UPLOAD", "WORKSPACE_FILE", "PASTED"]
    filename: str
    media_type: str
    size_bytes: int
    content_hash: str | None = None
    storage_key: str | None = None
    workspace_path: str | None = None
    extraction_state: Literal["PENDING", "EXTRACTED", "UNSUPPORTED", "FAILED"]
    extracted_text: str | None = None
    status: Literal["RESERVED", "ACTIVE", "REMOVED", "QUARANTINED"]
    created_by: UUID | None = None
    lock_version: int
    created_at: datetime
    updated_at: datetime
