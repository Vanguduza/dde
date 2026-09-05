"""Scoped, provenance-labelled DDE memory with durable object-backed bodies.

PostgreSQL owns scope/trust/promotion/index metadata. Durable bodies are
content-addressed through DDE object storage (R2 when configured, local in
non-production fallback). Recall ranks metadata/preview first and hydrates only
items that actually fit the turn budget.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.ai_memory_item import AiMemoryItem
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.fabric.repository import FabricRepository
from engine.fabric.tables import ai_memory_items
from engine.object_store.durable import ScopedObjectStore, scoped_object_store_from_env

MEMORY_INLINE_PREVIEW_CHARS = 2_048
DEFAULT_RECALL_BUDGET_TOKENS = 4_000
DEFAULT_MAX_RECALL_ITEMS = 8
DEFAULT_MAX_ITEM_TOKENS = 1_200
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "into",
        "have",
        "has",
        "are",
        "was",
        "were",
        "will",
        "must",
        "should",
        "when",
        "then",
        "than",
        "your",
        "you",
        "dde",
    }
)
_TRUST_WEIGHT = {"AUTHORITY": 1.0, "DERIVED": 0.82, "ADVISORY": 0.58, "UNKNOWN": 0.2}
_SCOPE_WEIGHT = {
    "CONVERSATION": 1.0,
    "MISSION": 0.95,
    "REPOSITORY": 0.90,
    "PROJECT": 0.84,
    "ORGANIZATION": 0.74,
    "USER": 0.70,
    "EPHEMERAL": 0.45,
}


@dataclass(frozen=True)
class MemoryRecallItem:
    memory_id: UUID
    scope_kind: str
    scope_ref: str
    trust_class: str
    source_type: str
    text: str
    estimated_tokens: int
    score: float
    truncated: bool
    storage_backend: str
    source_refs: tuple[str, ...]


@dataclass(frozen=True)
class MemoryRecallResult:
    items: tuple[MemoryRecallItem, ...]
    estimated_tokens: int
    budget_tokens: int
    considered: int
    omitted_memory_ids: tuple[UUID, ...]


def _token_estimate(text: str) -> int:
    return math.ceil(len(text) / 4) if text else 0


def _terms(text: str) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for match in _TOKEN_RE.finditer(text.lower()):
        token = match.group(0)
        if len(token) < 3 or token.isdigit() or token in _STOPWORDS:
            continue
        seen.setdefault(token, None)
        if len(seen) >= 16:
            break
    return tuple(seen)


def _preview(content: str) -> str:
    clean = content.strip()
    if len(clean) <= MEMORY_INLINE_PREVIEW_CHARS:
        return clean
    return (
        clean[: MEMORY_INLINE_PREVIEW_CHARS - 35].rstrip()
        + "\n… [object-backed memory body]"
    )


def _relevant_excerpt(
    text: str, terms: tuple[str, ...], max_tokens: int
) -> tuple[str, bool]:
    max_chars = max(256, max_tokens * 4)
    if len(text) <= max_chars:
        return text, False
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not paragraphs:
        return text[:max_chars], True
    ranked: list[tuple[int, int, str]] = []
    for index, paragraph in enumerate(paragraphs):
        lower = paragraph.lower()
        hits = sum(1 for term in terms if term in lower)
        ranked.append((hits, -index, paragraph))
    ranked.sort(reverse=True)
    chosen: list[tuple[int, str]] = []
    used = 0
    for _, neg_index, paragraph in ranked:
        if chosen and used + len(paragraph) + 2 > max_chars:
            continue
        take = paragraph[: max_chars - used]
        chosen.append((-neg_index, take))
        used += len(take) + 2
        if used >= max_chars:
            break
    chosen.sort(key=lambda entry: entry[0])
    excerpt = "\n\n".join(part for _, part in chosen).strip()
    return (excerpt or text[:max_chars]), True


class MemoryService:
    def __init__(
        self, engine: AsyncEngine, *, objects: ScopedObjectStore | None = None
    ) -> None:
        self.repo = FabricRepository(engine)
        self.objects = objects or scoped_object_store_from_env(namespace="memory")

    async def propose(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        scope_kind: str,
        scope_ref: str,
        content: str,
        source_type: str,
        source_refs: list[str],
        trust_class: str = "ADVISORY",
        proposed_by_profile_id: str | None = None,
        metadata: dict[str, object] | None = None,
        fresh_until: datetime | None = None,
    ) -> AiMemoryItem:
        return await self._create(
            tenant_id=tenant_id,
            project_id=project_id,
            scope_kind=scope_kind,
            scope_ref=scope_ref,
            content=content,
            source_type=source_type,
            source_refs=source_refs,
            trust_class=trust_class,
            status="CANDIDATE",
            proposed_by_profile_id=proposed_by_profile_id,
            metadata=metadata or {},
            fresh_until=fresh_until,
        )

    async def record_authority(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        scope_kind: str,
        scope_ref: str,
        content: str,
        source_type: str,
        source_refs: list[str],
        metadata: dict[str, object] | None = None,
    ) -> AiMemoryItem:
        if not source_refs:
            raise DdeError(
                "EVIDENCE_MISSING",
                "authoritative memory requires durable DDE source refs",
            )
        return await self._create(
            tenant_id=tenant_id,
            project_id=project_id,
            scope_kind=scope_kind,
            scope_ref=scope_ref,
            content=content,
            source_type=source_type,
            source_refs=source_refs,
            trust_class="AUTHORITY",
            status="APPROVED",
            proposed_by_profile_id=None,
            metadata=metadata or {},
            fresh_until=None,
        )

    async def approve(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        memory_id: UUID,
        principal_id: UUID,
        lock_version: int,
    ) -> AiMemoryItem:
        current = await self.get(
            tenant_id=tenant_id, project_id=project_id, memory_id=memory_id
        )
        if current.status != "CANDIDATE":
            raise DdeError("VERSION_CONFLICT", "only candidate memory can be approved")
        now = datetime.now(UTC)
        return await self.repo.update_locked(
            table=ai_memory_items,
            model=AiMemoryItem,
            id_column="memory_id",
            object_id=memory_id,
            tenant_id=tenant_id,
            project_id=project_id,
            lock_version=lock_version,
            values={
                "status": "APPROVED",
                "approved_by": principal_id,
                "approved_at": now,
                "updated_at": now,
            },
        )

    async def reject(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        memory_id: UUID,
        lock_version: int,
    ) -> AiMemoryItem:
        current = await self.get(
            tenant_id=tenant_id, project_id=project_id, memory_id=memory_id
        )
        if current.status != "CANDIDATE":
            raise DdeError("VERSION_CONFLICT", "only candidate memory can be rejected")
        return await self.repo.update_locked(
            table=ai_memory_items,
            model=AiMemoryItem,
            id_column="memory_id",
            object_id=memory_id,
            tenant_id=tenant_id,
            project_id=project_id,
            lock_version=lock_version,
            values={"status": "REJECTED", "updated_at": datetime.now(UTC)},
        )

    async def supersede(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        memory_id: UUID,
        replacement_content: str,
        source_refs: list[str],
        principal_id: UUID,
    ) -> AiMemoryItem:
        current = await self.get(
            tenant_id=tenant_id, project_id=project_id, memory_id=memory_id
        )
        if current.status != "APPROVED":
            raise DdeError("VERSION_CONFLICT", "only approved memory can be superseded")
        replacement = await self._create(
            tenant_id=tenant_id,
            project_id=project_id,
            scope_kind=current.scope_kind,
            scope_ref=current.scope_ref,
            content=replacement_content,
            source_type="SUPERSEDE",
            source_refs=source_refs,
            trust_class=current.trust_class,
            status="APPROVED",
            proposed_by_profile_id=None,
            metadata=current.metadata,
            fresh_until=current.fresh_until,
            approved_by=principal_id,
            supersedes_memory_id=current.memory_id,
        )
        await self.repo.update_locked(
            table=ai_memory_items,
            model=AiMemoryItem,
            id_column="memory_id",
            object_id=current.memory_id,
            tenant_id=tenant_id,
            project_id=project_id,
            lock_version=current.lock_version,
            values={"status": "SUPERSEDED", "updated_at": datetime.now(UTC)},
        )
        return replacement

    async def get(
        self, *, tenant_id: UUID, project_id: UUID, memory_id: UUID
    ) -> AiMemoryItem:
        return await self.repo.get_model(
            table=ai_memory_items,
            model=AiMemoryItem,
            id_column="memory_id",
            object_id=memory_id,
            tenant_id=tenant_id,
            project_id=project_id,
        )

    def read_content(
        self, memory: AiMemoryItem, *, max_bytes: int | None = None
    ) -> str:
        if memory.storage_key is None:
            body = memory.content.encode()
        else:
            body = self.objects.read(
                tenant_id=memory.tenant_id,
                project_id=memory.project_id,
                key=memory.storage_key,
                max_bytes=max_bytes,
            )
        digest = hashlib.sha256(body).hexdigest()
        if digest != memory.content_hash:
            raise DdeError(
                "VERSION_CONFLICT",
                "memory body hash no longer matches its durable metadata",
                retryable=False,
                details={"memory_id": str(memory.memory_id)},
            )
        try:
            return body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DdeError(
                "CONTEXT_INCOMPLETE", "memory body is not UTF-8 text"
            ) from exc

    async def list_scope(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        scope_kind: str,
        scope_ref: str,
        status: str | None = None,
    ) -> tuple[AiMemoryItem, ...]:
        filters: dict[str, object] = {"scope_kind": scope_kind, "scope_ref": scope_ref}
        if status:
            filters["status"] = status
        return await self.repo.list_models(
            table=ai_memory_items,
            model=AiMemoryItem,
            tenant_id=tenant_id,
            project_id=project_id,
            filters=filters,
            order_by=(ai_memory_items.c.updated_at.desc(),),
        )

    async def recall(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        query: str,
        scopes: list[tuple[str, str]],
        budget_tokens: int = DEFAULT_RECALL_BUDGET_TOKENS,
        max_items: int = DEFAULT_MAX_RECALL_ITEMS,
        max_item_tokens: int = DEFAULT_MAX_ITEM_TOKENS,
    ) -> MemoryRecallResult:
        if budget_tokens < 0 or max_items < 0 or max_item_tokens < 1:
            raise DdeError("VALIDATION_FAILED", "invalid memory recall budget")
        now = datetime.now(UTC)
        query_terms = _terms(query)
        scope_rank = {scope: index for index, scope in enumerate(scopes)}
        candidates: dict[UUID, tuple[float, AiMemoryItem]] = {}
        for scope_kind, scope_ref in scopes:
            for memory in await self.list_scope(
                tenant_id=tenant_id,
                project_id=project_id,
                scope_kind=scope_kind,
                scope_ref=scope_ref,
                status="APPROVED",
            ):
                if memory.fresh_until is not None and memory.fresh_until < now:
                    continue
                searchable = (
                    memory.content + " " + " ".join(memory.source_refs)
                ).lower()
                hits = sum(1 for term in query_terms if term in searchable)
                lexical = hits / max(1, len(query_terms)) if query_terms else 0.25
                trust = _TRUST_WEIGHT.get(memory.trust_class, 0.0)
                scope_weight = _SCOPE_WEIGHT.get(memory.scope_kind, 0.4)
                source_bonus = min(0.15, len(memory.source_refs) * 0.03)
                position_bonus = max(
                    0.0, 0.10 - scope_rank[(scope_kind, scope_ref)] * 0.01
                )
                score = (
                    lexical * 5.0
                    + trust * 4.0
                    + scope_weight * 3.0
                    + source_bonus
                    + position_bonus
                )
                candidates[memory.memory_id] = (score, memory)
        ranked = sorted(
            candidates.values(),
            key=lambda entry: (entry[0], entry[1].updated_at),
            reverse=True,
        )
        selected: list[MemoryRecallItem] = []
        omitted: list[UUID] = []
        used = 0
        for score, memory in ranked:
            if len(selected) >= max_items or used >= budget_tokens:
                omitted.append(memory.memory_id)
                continue
            remaining = budget_tokens - used
            allowance = min(max_item_tokens, remaining)
            if allowance <= 0:
                omitted.append(memory.memory_id)
                continue
            body = self.read_content(memory)
            excerpt, truncated = _relevant_excerpt(body, query_terms, allowance)
            tokens = min(_token_estimate(excerpt), allowance)
            if tokens <= 0:
                omitted.append(memory.memory_id)
                continue
            selected.append(
                MemoryRecallItem(
                    memory_id=memory.memory_id,
                    scope_kind=memory.scope_kind,
                    scope_ref=memory.scope_ref,
                    trust_class=memory.trust_class,
                    source_type=memory.source_type,
                    text=excerpt,
                    estimated_tokens=tokens,
                    score=score,
                    truncated=truncated,
                    storage_backend=memory.storage_backend,
                    source_refs=tuple(memory.source_refs),
                )
            )
            used += tokens
        return MemoryRecallResult(
            items=tuple(selected),
            estimated_tokens=used,
            budget_tokens=budget_tokens,
            considered=len(ranked),
            omitted_memory_ids=tuple(omitted),
        )

    async def _create(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        scope_kind: str,
        scope_ref: str,
        content: str,
        source_type: str,
        source_refs: list[str],
        trust_class: str,
        status: str,
        proposed_by_profile_id: str | None,
        metadata: dict[str, object],
        fresh_until: datetime | None,
        approved_by: UUID | None = None,
        supersedes_memory_id: UUID | None = None,
    ) -> AiMemoryItem:
        clean_scope = scope_ref.strip()
        clean_content = content.strip()
        if not clean_scope or not clean_content:
            raise DdeError("VALIDATION_FAILED", "memory scope and content are required")
        body = clean_content.encode("utf-8")
        digest = hashlib.sha256(body).hexdigest()
        storage_key: str | None = None
        storage_backend = "INLINE"
        inline = clean_content
        if scope_kind != "EPHEMERAL":
            storage_key = self.objects.put(
                tenant_id=tenant_id,
                project_id=project_id,
                content_hash=digest,
                content=body,
            )
            storage_backend = self.objects.backend_name
            inline = _preview(clean_content)
        now = datetime.now(UTC)
        values: dict[str, object] = {
            "memory_id": uuid7(),
            "tenant_id": tenant_id,
            "project_id": project_id,
            "scope_kind": scope_kind,
            "scope_ref": clean_scope,
            "trust_class": trust_class,
            "status": status,
            "content": inline,
            "content_hash": digest,
            "content_size_bytes": len(body),
            "token_estimate": _token_estimate(clean_content),
            "storage_backend": storage_backend,
            "storage_key": storage_key,
            "source_type": source_type,
            "source_refs": source_refs,
            "proposed_by_profile_id": proposed_by_profile_id,
            "approved_by": approved_by,
            "approved_at": now if approved_by else None,
            "supersedes_memory_id": supersedes_memory_id,
            "fresh_until": fresh_until,
            "metadata": metadata,
            "lock_version": 1,
            "created_at": now,
            "updated_at": now,
        }
        AiMemoryItem.model_validate(values)
        return await self.repo.insert_model(
            table=ai_memory_items,
            model=AiMemoryItem,
            tenant_id=tenant_id,
            project_id=project_id,
            values=values,
        )
