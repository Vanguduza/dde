# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SourceArtifact(BaseModel):
    """
    Immutable domain-neutral source artifact metadata and content-addressed provenance.
    """

    model_config = ConfigDict(extra="forbid")

    artifact_id: UUID
    source_id: UUID
    tenant_id: UUID
    project_id: UUID
    parent_artifact_id: UUID | None = None
    artifact_kind: str
    provider_artifact_key: str
    title: str
    source_uri: str | None = None
    revision: str
    content_hash: str
    content_object_ref: str | None = None
    content_object_backend: str | None = None
    content_size_bytes: int | None = None
    media_type: str | None = None
    metadata: dict[str, object]
    provenance: dict[str, object]
    created_at: datetime
    updated_at: datetime
