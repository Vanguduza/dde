# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ContextPackage(BaseModel):
    """
    Versioned compiled context. Definition is immutable; lifecycle lives in status.
    """

    model_config = ConfigDict(extra="forbid")

    package_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID
    version: int
    assembly_hash: str
    assembly_tokens: int
    index_version: str
    index_lag_commits: int
    coverage: dict[str, object]
    status: str
    retrievers_used: list[str]
    created_at: datetime
    updated_at: datetime
