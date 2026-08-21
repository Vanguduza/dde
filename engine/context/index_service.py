"""Chapter 5.4 index lifecycle for the semantic retriever.

The semantic index is a per-project store of syntactic chunks and their
versioned embeddings. `ContextIndexService` owns the lifecycle:

- `build_index` — full index (new `index_version`, every file chunked +
  embedded), the "Build" rule.
- `reindex_incremental` — re-chunks the corpus but persists only changed
  chunks and tombstones chunks whose file disappeared, the "Incremental
  update" + "Invalidation" + "Deletion" rules.
- `change_embedding_model` — backfills every current chunk into a NEW
  `index_version` under a new embedding model without switching; the
  "Embedding model version" + "two index versions may coexist" rules.
- `activate_index` — the explicit switch to a backfilled version (the
  blueprint defers the switch until the eval corpus shows no regression —
  Chapter 5.13 / DDE-032 — so the *switch* is a distinct call site, not
  automatic).

**Deferred (EDR).** The *triggers* are not wired: full build on project
registration, incremental reindex on every integrated commit (Chapter 10
integration manager). Both call sites exist here and are the production
mutation path; the schedulers that invoke them are out of this mission's
scope. Structural dependents (import-graph closure) are not re-indexed —
there is no import graph (the same substitution `engine.context.retrievers.
structural` documents). Background backfill is synchronous here; a true
async worker is deferred.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.context.chunking import Chunk, chunk_file
from engine.context.embeddings import EMBEDDING_MODEL_VERSION, embed
from engine.context.index_repository import ContextIndexRepository
from engine.context.repo import current_commit_sha, is_excluded, repo_root
from engine.contracts.context_chunk import ContextChunk
from engine.contracts.context_index import ContextIndex
from engine.core.clock import Clock, SystemClock
from engine.core.ids import uuid7
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")

DEFAULT_INDEX_LAG_WARN_COMMITS = 10
DEFAULT_INDEX_LAG_BLOCK_COMMITS = 50

INDEX_STATUS_ACTIVE = "ACTIVE"
INDEX_STATUS_BACKFILLING = "BACKFILLING"


@dataclass(frozen=True)
class IndexState:
    """The active index plus its staleness, for `ContextService.compile`."""

    index: ContextIndex
    lag_commits: int


@dataclass(frozen=True)
class IndexedChunk:
    """A chunk plus its embedding, the unit persisted in `context_chunks`."""

    chunk: Chunk
    embedding: list[float]
    embedding_model_version: str


def _commit_lag(root: Path, older: str, newer: str) -> int:
    """Commits between `older` and `newer`, via `git rev-list --count`.

    Best-effort: returns 0 when the two refs are equal, unreadable, or git
    is unavailable. A caller that needs to prove non-staleness on an
    unreadable history must treat this conservatively itself.
    """
    if older in ("", "unknown") or newer in ("", "unknown") or older == newer:
        return 0
    git = shutil.which("git")
    if git is None:
        return 0
    try:
        result = subprocess.run(  # noqa: S603
            [git, "rev-list", "--count", f"{older}..{newer}"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 0
    if result.returncode != 0 or not result.stdout.strip().isdigit():
        return 0
    return int(result.stdout.strip())


def staleness_action(
    lag_commits: int,
    *,
    warn_threshold: int = DEFAULT_INDEX_LAG_WARN_COMMITS,
    block_threshold: int = DEFAULT_INDEX_LAG_BLOCK_COMMITS,
) -> str:
    """Chapter 5.4 staleness: `"ok"`, `"warn"`, or `"block"`."""
    if lag_commits > block_threshold:
        return "block"
    if lag_commits > warn_threshold:
        return "warn"
    return "ok"


class ContextIndexService:
    """Async, PostgreSQL-backed writer for `context_indexes` and
    `context_chunks` (Chapter 5.4)."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: ContextIndexRepository | None = None,
        clock: Clock | None = None,
        root: Path | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or ContextIndexRepository()
        self._clock = clock or SystemClock()
        self._root = root or repo_root()

    async def _run(
        self,
        uow: PostgresUnitOfWork | None,
        tenant_id: UUID,
        project_id: UUID,
        body: Callable[[PostgresUnitOfWork], Awaitable[T]],
    ) -> T:
        if uow is not None:
            return await body(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as owned:
            result = await body(owned)
            await owned.commit()
            return result

    def _collect_chunks(self, root: Path) -> list[Chunk]:
        chunks: list[Chunk] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            if is_excluded(rel):
                continue
            chunks.extend(chunk_file(path, rel.as_posix()))
        return chunks

    def _embed_all(
        self, chunks: list[Chunk], *, model_version: str
    ) -> list[IndexedChunk]:
        return [
            IndexedChunk(
                chunk=chunk,
                embedding=embed(chunk.content, model_version=model_version),
                embedding_model_version=model_version,
            )
            for chunk in chunks
        ]

    def _records(
        self,
        indexed: list[IndexedChunk],
        *,
        tenant_id: UUID,
        project_id: UUID,
        index_version: str,
        commit_sha: str,
    ) -> list[ContextChunk]:
        now = self._clock.now()
        return [
            ContextChunk(
                chunk_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                index_version=index_version,
                embedding_model_version=item.embedding_model_version,
                file_path=item.chunk.file_path,
                symbol_path=item.chunk.symbol_path,
                content_hash=item.chunk.content_hash,
                start_line=item.chunk.start_line,
                end_line=item.chunk.end_line,
                language=item.chunk.language,
                commit_sha=commit_sha,
                content=item.chunk.content,
                embedding=item.embedding,
                current=True,
                created_at=now,
                updated_at=now,
            )
            for item in indexed
        ]

    async def build_index(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> ContextIndex:
        """Chapter 5.4 "Build": a full index under a fresh `index_version`."""
        root = self._root
        commit_sha = current_commit_sha(root)
        index_version = str(uuid7())

        async def _op(active: PostgresUnitOfWork) -> ContextIndex:
            chunks = self._collect_chunks(root)
            indexed = self._embed_all(chunks, model_version=EMBEDDING_MODEL_VERSION)
            records = self._records(
                indexed,
                tenant_id=tenant_id,
                project_id=project_id,
                index_version=index_version,
                commit_sha=commit_sha,
            )
            await self._repository.insert_chunks(active.connection, records)
            now = self._clock.now()
            index = ContextIndex(
                index_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                current_version=index_version,
                embedding_model_version=EMBEDDING_MODEL_VERSION,
                head_commit_sha=commit_sha,
                status=INDEX_STATUS_ACTIVE,
                created_at=now,
                updated_at=now,
            )
            await self._repository.upsert_index(active.connection, index)
            return index

        return await self._run(uow, tenant_id, project_id, _op)

    async def reindex_incremental(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> ContextIndex:
        """Chapter 5.4 "Incremental update" + "Invalidation" + "Deletion":
        persists only changed chunks and tombstones vanished chunks under the
        current `index_version`."""
        root = self._root
        commit_sha = current_commit_sha(root)

        async def _op(active: PostgresUnitOfWork) -> ContextIndex:
            current = await self._repository.get_index(
                active.connection, tenant_id, project_id
            )
            if current is None:
                return await self.build_index(
                    tenant_id=tenant_id, project_id=project_id, uow=active
                )
            index_version = current.current_version
            existing = await self._repository.list_current_chunks(
                active.connection, tenant_id, project_id, index_version
            )
            existing_by_identity = {
                (chunk.file_path, chunk.symbol_path): chunk for chunk in existing
            }
            fresh = self._collect_chunks(root)
            fresh_by_identity: dict[tuple[str, str], Chunk] = {}
            for chunk in fresh:
                fresh_by_identity[(chunk.file_path, chunk.symbol_path)] = chunk

            to_insert: list[IndexedChunk] = []
            to_tombstone: list[UUID] = []
            for identity, existing_chunk in existing_by_identity.items():
                if identity not in fresh_by_identity:
                    to_tombstone.append(existing_chunk.chunk_id)
            for identity, fresh_chunk in fresh_by_identity.items():
                prior = existing_by_identity.get(identity)
                if prior is not None and (
                    prior.content_hash == fresh_chunk.content_hash
                ):
                    continue
                if prior is not None:
                    to_tombstone.append(prior.chunk_id)
                to_insert.append(
                    IndexedChunk(
                        chunk=fresh_chunk,
                        embedding=embed(
                            fresh_chunk.content,
                            model_version=current.embedding_model_version,
                        ),
                        embedding_model_version=current.embedding_model_version,
                    )
                )

            await self._repository.tombstone_chunks(active.connection, to_tombstone)
            records = self._records(
                to_insert,
                tenant_id=tenant_id,
                project_id=project_id,
                index_version=index_version,
                commit_sha=commit_sha,
            )
            await self._repository.insert_chunks(active.connection, records)
            now = self._clock.now()
            updated = ContextIndex(
                index_id=current.index_id,
                tenant_id=current.tenant_id,
                project_id=current.project_id,
                current_version=current.current_version,
                embedding_model_version=current.embedding_model_version,
                head_commit_sha=commit_sha,
                status=current.status,
                created_at=current.created_at,
                updated_at=now,
            )
            await self._repository.upsert_index(active.connection, updated)
            return updated

        return await self._run(uow, tenant_id, project_id, _op)

    async def change_embedding_model(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        model_version: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> str:
        """Chapter 5.4 "Embedding model version": backfills every current
        chunk into a NEW `index_version` under `model_version` WITHOUT
        switching. Returns the new `index_version`; `activate_index` is the
        explicit, eval-gated switch."""
        root = self._root
        commit_sha = current_commit_sha(root)
        new_version = str(uuid7())

        async def _op(active: PostgresUnitOfWork) -> str:
            current = await self._repository.get_index(
                active.connection, tenant_id, project_id
            )
            if current is None:
                await self.build_index(
                    tenant_id=tenant_id, project_id=project_id, uow=active
                )
                current = await self._repository.get_index(
                    active.connection, tenant_id, project_id
                )
            if current is None:
                raise ValueError("no context index exists to backfill")
            existing = await self._repository.list_current_chunks(
                active.connection, tenant_id, project_id, current.current_version
            )
            records = self._records(
                [
                    IndexedChunk(
                        chunk=Chunk(
                            file_path=chunk.file_path,
                            symbol_path=chunk.symbol_path,
                            start_line=chunk.start_line,
                            end_line=chunk.end_line,
                            language=chunk.language,
                            content=chunk.content,
                        ),
                        embedding=embed(chunk.content, model_version=model_version),
                        embedding_model_version=model_version,
                    )
                    for chunk in existing
                ],
                tenant_id=tenant_id,
                project_id=project_id,
                index_version=new_version,
                commit_sha=commit_sha,
            )
            await self._repository.insert_chunks(active.connection, records)
            return new_version

        return await self._run(uow, tenant_id, project_id, _op)

    async def activate_index(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        index_version: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> ContextIndex:
        """Switch the active index to a backfilled `index_version`."""

        async def _op(active: PostgresUnitOfWork) -> ContextIndex:
            current = await self._repository.get_index(
                active.connection, tenant_id, project_id
            )
            if current is None:
                raise ValueError("no context index exists to activate")
            chunks = await self._repository.list_current_chunks(
                active.connection, tenant_id, project_id, index_version
            )
            if not chunks:
                raise ValueError(f"no chunks exist under index_version {index_version}")
            model_version = chunks[0].embedding_model_version
            now = self._clock.now()
            updated = ContextIndex(
                index_id=current.index_id,
                tenant_id=current.tenant_id,
                project_id=current.project_id,
                current_version=index_version,
                embedding_model_version=model_version,
                head_commit_sha=current.head_commit_sha,
                status=INDEX_STATUS_ACTIVE,
                created_at=current.created_at,
                updated_at=now,
            )
            await self._repository.upsert_index(active.connection, updated)
            return updated

        return await self._run(uow, tenant_id, project_id, _op)

    async def load_state(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> IndexState | None:
        """The active index plus its commit lag versus the workspace head —
        the Chapter 5.4 staleness input for `ContextService.compile`."""

        async def _op(active: PostgresUnitOfWork) -> IndexState | None:
            index = await self._repository.get_index(
                active.connection, tenant_id, project_id
            )
            if index is None:
                return None
            head = current_commit_sha(self._root)
            lag = _commit_lag(self._root, index.head_commit_sha, head)
            return IndexState(index=index, lag_commits=lag)

        return await self._run(uow, tenant_id, project_id, _op)
