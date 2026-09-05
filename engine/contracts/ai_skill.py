# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AiSkill(BaseModel):
    """Versioned candidate/evaluated/certified skill supply-chain artifact."""

    model_config = ConfigDict(extra="forbid")

    skill_id: UUID
    tenant_id: UUID
    project_id: UUID
    slug: str
    version: str
    title: str
    description: str
    instructions: str
    source_kind: Literal[
        "DDE_NATIVE",
        "HERMES",
        "CLAUDE",
        "CODEX",
        "MCP",
        "PLUGIN",
        "USER",
        "EXTERNAL",
    ]
    source_ref: str | None = None
    provenance_refs: list[str]
    license: str | None = None
    manifest_hash: str
    required_capability_ids: list[str]
    toolset_ids: list[str]
    status: Literal["CANDIDATE", "EVALUATING", "CERTIFIED", "REJECTED", "RETIRED"]
    evaluation_refs: list[str]
    certified_by: UUID | None = None
    certified_at: datetime | None = None
    parent_skill_id: UUID | None = None
    lock_version: int
    created_at: datetime
    updated_at: datetime
