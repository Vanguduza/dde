# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DesignSourceArtifact(BaseModel):
    """
    DDE-069 M8 normalized source candidate. Indexed previews may lack bytes;
    fetched/admitted artifacts require a content hash and remain isolated from accepted
    production.
    """

    model_config = ConfigDict(extra="forbid")

    artifact_id: UUID
    source_id: UUID
    search_run_id: UUID | None = None
    tenant_id: UUID
    project_id: UUID
    provider_artifact_key: str
    artifact_kind: Literal[
        "COMPONENT",
        "TEMPLATE",
        "THEME",
        "FOUNDATION",
        "DIRECTIVE",
        "REFERENCE",
    ]
    title: str
    source_uri: str | None = None
    version_ref: str | None = None
    content_hash: str | None = None
    content_object_ref: str | None = None
    content_object_backend: str | None = None
    content_size_bytes: int | None = None
    framework: str | None = None
    supported_archetypes: list[str]
    dependency_manifest: list[str]
    license_state: Literal[
        "OPEN_REUSE",
        "CONDITIONAL_REUSE",
        "REFERENCE_ONLY",
        "REJECTED",
        "UNKNOWN",
    ]
    license_ids: list[str]
    security_state: Literal["PASS", "FAIL", "UNKNOWN"]
    accessibility_state: Literal["PASS", "FAIL", "PARTIAL", "UNKNOWN"]
    compatibility_state: Literal["PASS", "FAIL", "PARTIAL", "UNKNOWN"]
    retrieval_state: Literal[
        "INDEXED",
        "INSPECTED",
        "FETCHED",
        "ADMITTED",
        "REJECTED",
        "BLOCKED",
    ]
    metadata: dict[str, object]
    created_at: datetime
    updated_at: datetime
