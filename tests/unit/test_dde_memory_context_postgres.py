from __future__ import annotations

from pathlib import Path

import pytest

from engine.chat.service import FrontendChatService
from engine.fabric.context import ContextSnapshotService
from engine.fabric.memory import MemoryService
from engine.object_store.durable import LocalScopedObjectStore
from tests.support.db import new_engine, seed_tenant


@pytest.mark.asyncio
async def test_dde_memory_and_context_snapshot_persist_with_object_lineage(
    tmp_path: Path,
) -> None:
    """Production-DB proof for shared memory metadata + durable object lineage.

    This test intentionally uses the ordinary PostgreSQL/RLS helpers. On hosts
    without DDE_DATABASE_URL it is infrastructure-UNAVAILABLE rather than a
    substitute SQLite/local metadata pass.
    """
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        chat = FrontendChatService(engine)
        conversation = await chat.open(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            title="Shared memory persistence",
            created_by=fixture.principal_id,
        )
        memory = MemoryService(
            engine,
            objects=LocalScopedObjectStore(
                namespace="memory", root=tmp_path / "objects"
            ),
        )
        stored = await memory.record_authority(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            scope_kind="CONVERSATION",
            scope_ref=str(conversation.conversation_id),
            content="Verification must bind the exact candidate content hash.",
            source_type="EVIDENCE",
            source_refs=["evidence:dde-069:test"],
        )
        assert stored.storage_backend == "LOCAL"
        assert stored.storage_key is not None
        assert memory.read_content(stored).startswith("Verification must bind")

        contexts = ContextSnapshotService(
            engine,
            objects=LocalScopedObjectStore(
                namespace="context", root=tmp_path / "objects"
            ),
        )
        snapshot = await contexts.create(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            conversation_id=conversation.conversation_id,
            reason="TURN",
            retained_refs=[f"memory:{stored.memory_id}"],
            omitted_refs=[],
            omission_reasons={},
            item_manifest=[
                {
                    "kind": "MEMORY",
                    "ref": f"memory:{stored.memory_id}",
                    "tokens": stored.token_estimate,
                }
            ],
            estimated_tokens=stored.token_estimate,
            budget_tokens=24_000,
        )
        assert snapshot.archive_storage_backend == "LOCAL"
        assert snapshot.archive_storage_key is not None
        latest = await contexts.latest(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            conversation_id=conversation.conversation_id,
        )
        assert latest is not None
        assert latest.context_snapshot_id == snapshot.context_snapshot_id
    finally:
        await engine.dispose()
