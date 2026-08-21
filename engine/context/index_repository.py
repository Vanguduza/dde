"""Async repository for `context_indexes` and `context_chunks` (Chapter 5.4).

Reads and writes execute on the connection of an already-open unit of work
(Chapter 3.5); this module never begins or ends a transaction itself.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.context.tables import context_chunks, context_indexes
from engine.contracts.context_chunk import ContextChunk
from engine.contracts.context_index import ContextIndex


class ContextIndexRepository:
    """Reads and writes the Chapter 5.4 semantic index tables."""

    async def get_index(
        self, connection: AsyncConnection, tenant_id: UUID, project_id: UUID
    ) -> ContextIndex | None:
        result = await connection.execute(
            select(context_indexes).where(
                context_indexes.c.tenant_id == tenant_id,
                context_indexes.c.project_id == project_id,
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return ContextIndex.model_validate(dict(row))

    async def upsert_index(
        self, connection: AsyncConnection, index: ContextIndex
    ) -> None:
        stmt = pg_insert(context_indexes).values(**index.model_dump())
        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "project_id"],
            set_={
                "current_version": stmt.excluded.current_version,
                "embedding_model_version": stmt.excluded.embedding_model_version,
                "head_commit_sha": stmt.excluded.head_commit_sha,
                "status": stmt.excluded.status,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await connection.execute(stmt)

    async def insert_chunks(
        self, connection: AsyncConnection, chunks: list[ContextChunk]
    ) -> None:
        if not chunks:
            return
        await connection.execute(
            context_chunks.insert(),
            [chunk.model_dump() for chunk in chunks],
        )

    async def list_current_chunks(
        self,
        connection: AsyncConnection,
        tenant_id: UUID,
        project_id: UUID,
        index_version: str,
    ) -> list[ContextChunk]:
        result = await connection.execute(
            select(context_chunks)
            .where(
                context_chunks.c.tenant_id == tenant_id,
                context_chunks.c.project_id == project_id,
                context_chunks.c.index_version == index_version,
                context_chunks.c.current.is_(True),
            )
            .order_by(context_chunks.c.file_path.asc())
        )
        return [
            ContextChunk.model_validate(dict(row)) for row in result.mappings().all()
        ]

    async def tombstone_chunks(
        self, connection: AsyncConnection, chunk_ids: list[UUID]
    ) -> None:
        if not chunk_ids:
            return
        await connection.execute(
            context_chunks.update()
            .where(context_chunks.c.chunk_id.in_(chunk_ids))
            .values(current=False)
        )
