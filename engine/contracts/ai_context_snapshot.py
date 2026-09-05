# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AiContextSnapshot(BaseModel):
    """
    Inspectable universal DDE context/compaction snapshot with retained/omitted
    provenance and content-addressed durable archive (R2 when configured).
    """

    model_config = ConfigDict(extra="forbid")

    context_snapshot_id: UUID
    tenant_id: UUID
    project_id: UUID
    conversation_id: UUID
    turn_id: UUID | None = None
    predecessor_snapshot_id: UUID | None = None
    reason: Literal[
        "TURN",
        "CHECKPOINT",
        "PRE_COMPACTION",
        "POST_COMPACTION",
        "RESUME",
        "PROVIDER_HANDOFF",
    ]
    summary: str | None = None
    retained_refs: list[str]
    omitted_refs: list[str]
    omission_reasons: dict[str, object]
    item_manifest: list[dict[str, object]]
    estimated_tokens: int
    budget_tokens: int
    context_hash: str
    archive_storage_backend: Literal["LOCAL", "R2"] | None = None
    archive_storage_key: str | None = None
    archive_hash: str | None = None
    archive_size_bytes: int | None = None
    created_at: datetime
    updated_at: datetime
