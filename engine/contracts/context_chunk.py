# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ContextChunk(BaseModel):
    """
    One syntactically-bounded code/document chunk and its versioned embedding (Chapter
    5.3, 5.4). Chunk identity is (file_path, symbol_path, content_hash); a changed hash
    invalidates the chunk and its embeddings.
    """

    model_config = ConfigDict(extra="forbid")

    chunk_id: UUID
    tenant_id: UUID
    project_id: UUID
    index_version: str
    embedding_model_version: str
    file_path: str
    symbol_path: str
    content_hash: str
    start_line: int
    end_line: int
    language: str
    commit_sha: str
    content: str
    embedding: list[float]
    current: bool
    created_at: datetime
    updated_at: datetime
