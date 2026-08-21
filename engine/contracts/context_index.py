# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ContextIndex(BaseModel):
    """
    Per-project semantic index state (Chapter 5.4): the currently active index_version,
    its embedding model version, and the workspace commit the index reflects (the anchor
    for index_lag_commits).
    """

    model_config = ConfigDict(extra="forbid")

    index_id: UUID
    tenant_id: UUID
    project_id: UUID
    current_version: str
    embedding_model_version: str
    head_commit_sha: str
    status: str
    created_at: datetime
    updated_at: datetime
