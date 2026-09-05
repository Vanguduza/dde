# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AiMemoryItem(BaseModel):
    """
    Scoped provenance-labelled universal DDE memory. Full durable bodies are content-
    addressed in DDE object storage (R2 when configured); PostgreSQL retains bounded
    recall preview, scope/trust/index metadata and storage lineage. Provider proposals
    enter CANDIDATE and never self-promote.
    """

    model_config = ConfigDict(extra="forbid")

    memory_id: UUID
    tenant_id: UUID
    project_id: UUID
    scope_kind: Literal[
        "USER",
        "ORGANIZATION",
        "PROJECT",
        "REPOSITORY",
        "MISSION",
        "CONVERSATION",
        "EPHEMERAL",
    ]
    scope_ref: str
    trust_class: Literal["AUTHORITY", "DERIVED", "ADVISORY", "UNKNOWN"]
    status: Literal["CANDIDATE", "APPROVED", "REJECTED", "SUPERSEDED"]
    content: str
    content_hash: str
    content_size_bytes: int
    token_estimate: int
    storage_backend: Literal["INLINE", "LOCAL", "R2"]
    storage_key: str | None = None
    source_type: str
    source_refs: list[str]
    proposed_by_profile_id: str | None = None
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    supersedes_memory_id: UUID | None = None
    fresh_until: datetime | None = None
    metadata: dict[str, object]
    lock_version: int
    created_at: datetime
    updated_at: datetime
