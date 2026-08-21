"""Semantic retriever (Chapter 5.2): cosine similarity over the chunk
embedding index (Chapter 5.4).

This is the semantic-retriever *slot* in the Chapter 5.1 pipeline. Its
current embedding is the deterministic hashing-trick vector from
`engine.context.embeddings` — a lexical feature vector, not a transformer
embedding (see that module's flagged divergence). Cosine similarity over it
surfaces lexically-overlapping code (Chapter 5.7's "semantically-similar-
but-unlinked code" eviction tier) as a distinct, fusionable signal. The
swap to a true semantic embedding is a `EMBEDDING_MODEL_VERSION` bump plus
re-index, not a retriever rewrite.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncConnection

from engine.context.embeddings import cosine_similarity, embed
from engine.context.index_repository import ContextIndexRepository
from engine.context.model import AUTHORITY_RANK_CODE, ContextItem
from engine.context.repo import classify_categories, touches_scope
from engine.contracts.task import Task

MAX_RESULT_ITEMS = 10


def _query_text(task: Task) -> str:
    return " ".join([task.title, task.intent, *task.success_criteria])


async def retrieve(
    connection: AsyncConnection,
    *,
    tenant_id: UUID,
    project_id: UUID,
    index_version: str,
    task: Task,
    expected_write_scope: tuple[str, ...],
    limit: int = MAX_RESULT_ITEMS,
    repository: ContextIndexRepository | None = None,
) -> list[ContextItem]:
    """Return the top-`limit` current chunks by cosine similarity to the
    task query, as `ContextItem`s keyed the same as the structural retriever
    so Chapter 5.3 fusion merges co-surfaced symbols."""
    repo = repository or ContextIndexRepository()
    query_vector = embed(_query_text(task))
    chunks = await repo.list_current_chunks(
        connection, tenant_id, project_id, index_version
    )
    scored = [
        (cosine_similarity(query_vector, chunk.embedding), chunk) for chunk in chunks
    ]
    scored.sort(key=lambda entry: (-entry[0], entry[1].file_path, entry[1].symbol_path))
    items: list[ContextItem] = []
    for rank, (score, chunk) in enumerate(scored[:limit], start=1):
        if score <= 0.0:
            continue
        content = (
            f"{chunk.file_path}::{chunk.symbol_path} "
            f"(lines {chunk.start_line}-{chunk.end_line})\n{chunk.content}"
        )
        items.append(
            ContextItem(
                retriever="semantic",
                key=f"symbol:{chunk.file_path}::{chunk.symbol_path}",
                categories=classify_categories(chunk.file_path, chunk.content),
                authority_rank=AUTHORITY_RANK_CODE,
                rank_in_retriever=rank,
                relevance=score,
                write_scope_match=touches_scope(chunk.file_path, expected_write_scope),
                content=content,
                source_path=chunk.file_path,
            )
        )
    return items
