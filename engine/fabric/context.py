"""Inspectable context snapshots and compaction lineage."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.ai_context_snapshot import AiContextSnapshot
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.fabric.repository import FabricRepository
from engine.fabric.tables import ai_context_snapshots
from engine.object_store.durable import ScopedObjectStore, scoped_object_store_from_env


def context_snapshot_hash(
    *,
    retained_refs: list[str],
    omitted_refs: list[str],
    item_manifest: list[dict[str, object]],
    summary: str | None,
) -> str:
    payload = {
        "retained": retained_refs,
        "omitted": omitted_refs,
        "items": item_manifest,
        "summary": summary,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


class ContextSnapshotService:
    def __init__(
        self, engine: AsyncEngine, *, objects: ScopedObjectStore | None = None
    ) -> None:
        self.repo = FabricRepository(engine)
        self.objects = objects or scoped_object_store_from_env(namespace="context")

    async def create(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        reason: str,
        retained_refs: list[str],
        omitted_refs: list[str],
        omission_reasons: dict[str, str],
        item_manifest: list[dict[str, object]],
        estimated_tokens: int,
        budget_tokens: int,
        summary: str | None = None,
        turn_id: UUID | None = None,
        predecessor_snapshot_id: UUID | None = None,
    ) -> AiContextSnapshot:
        if estimated_tokens < 0 or budget_tokens < 1:
            raise DdeError("VALIDATION_FAILED", "invalid context token accounting")
        unknown_reasons = sorted(set(omission_reasons) - set(omitted_refs))
        if unknown_reasons:
            raise DdeError(
                "VALIDATION_FAILED",
                "omission reason references non-omitted context",
                details={"refs": unknown_reasons},
            )
        if reason in {"PRE_COMPACTION", "POST_COMPACTION"} and not summary:
            raise DdeError(
                "CONTEXT_INCOMPLETE",
                "compaction snapshot requires an inspectable summary",
            )
        now = datetime.now(UTC)
        archive_payload = {
            "reason": reason,
            "summary": summary,
            "retained_refs": retained_refs,
            "omitted_refs": omitted_refs,
            "omission_reasons": omission_reasons,
            "item_manifest": item_manifest,
            "estimated_tokens": estimated_tokens,
            "budget_tokens": budget_tokens,
        }
        archive_bytes = json.dumps(
            archive_payload, sort_keys=True, ensure_ascii=False, default=str
        ).encode("utf-8")
        archive_hash = hashlib.sha256(archive_bytes).hexdigest()
        archive_key = self.objects.put(
            tenant_id=tenant_id,
            project_id=project_id,
            content_hash=archive_hash,
            content=archive_bytes,
        )
        values: dict[str, object] = {
            "context_snapshot_id": uuid7(),
            "tenant_id": tenant_id,
            "project_id": project_id,
            "conversation_id": conversation_id,
            "turn_id": turn_id,
            "predecessor_snapshot_id": predecessor_snapshot_id,
            "reason": reason,
            "summary": summary,
            "retained_refs": retained_refs,
            "omitted_refs": omitted_refs,
            "omission_reasons": omission_reasons,
            "item_manifest": item_manifest,
            "estimated_tokens": estimated_tokens,
            "budget_tokens": budget_tokens,
            "context_hash": context_snapshot_hash(
                retained_refs=retained_refs,
                omitted_refs=omitted_refs,
                item_manifest=item_manifest,
                summary=summary,
            ),
            "archive_storage_backend": self.objects.backend_name,
            "archive_storage_key": archive_key,
            "archive_hash": archive_hash,
            "archive_size_bytes": len(archive_bytes),
            "created_at": now,
            "updated_at": now,
        }
        AiContextSnapshot.model_validate(values)
        return await self.repo.insert_model(
            table=ai_context_snapshots,
            model=AiContextSnapshot,
            tenant_id=tenant_id,
            project_id=project_id,
            values=values,
        )

    async def latest(
        self, *, tenant_id: UUID, project_id: UUID, conversation_id: UUID
    ) -> AiContextSnapshot | None:
        rows = await self.repo.list_models(
            table=ai_context_snapshots,
            model=AiContextSnapshot,
            tenant_id=tenant_id,
            project_id=project_id,
            filters={"conversation_id": conversation_id},
            order_by=(ai_context_snapshots.c.created_at.desc(),),
            limit=1,
        )
        return rows[0] if rows else None

    async def list_for_conversation(
        self, *, tenant_id: UUID, project_id: UUID, conversation_id: UUID
    ) -> tuple[AiContextSnapshot, ...]:
        return await self.repo.list_models(
            table=ai_context_snapshots,
            model=AiContextSnapshot,
            tenant_id=tenant_id,
            project_id=project_id,
            filters={"conversation_id": conversation_id},
            order_by=(ai_context_snapshots.c.created_at.desc(),),
        )
