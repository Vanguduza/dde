"""Chapter 5.4 semantic index lifecycle + semantic retriever, tested against
a real PostgreSQL schema (Chapter 19.1) and a small, fully-controlled
synthetic working tree (not this live repository).

Covers the four lifecycle operations the blueprint requires — Build,
Incremental update (+ invalidation/deletion), Embedding-model change, and
Activation — plus the Chapter 5.4 staleness gate that `ContextService.
compile()` applies, and the semantic retriever's production slot in the
Chapter 5.1 pipeline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from engine.context.embeddings import EMBEDDING_MODEL_VERSION
from engine.context.index_repository import ContextIndexRepository
from engine.context.index_service import (
    ContextIndexService,
    IndexState,
    staleness_action,
)
from engine.context.model import ContextBudgetExceeded
from engine.context.retrievers import semantic
from engine.context.service import ContextService
from engine.contracts.context_index import ContextIndex
from engine.contracts.task import Task
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.truth.db import open_unit_of_work
from tests.support.context_fixtures import build_context_fixture, build_fake_repo
from tests.support.db import new_engine, seed_tenant

_NEW_MODEL_VERSION = "dde-hash-trick-v2"


def _task(tenant_id: Any, project_id: Any, **overrides: object) -> Task:
    now = datetime.now(UTC)
    defaults: dict[str, object] = dict(
        task_id=uuid7(),
        tenant_id=tenant_id,
        project_id=project_id,
        mission_id=uuid7(),
        graph_id=uuid7(),
        title="Assembly hash determinism",
        intent="sha256_hex hashing tenant credential handling",
        task_class="verification",
        requirement_refs=[],
        feature_refs=[],
        success_criteria=["Recompiling identical inputs yields the same hash"],
        expected_write_scope=["engine/context"],
        expected_read_scope=["engine/context/hashing.py"],
        blast_radius="local",
        risk_class="low",
        estimated_effort="s",
        autonomy_ceiling=2,
        requires_approval=False,
        status="CREATED",
        lock_version=1,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return Task.model_validate(defaults)


class _FixedLagIndexService(ContextIndexService):
    """Returns a fixed `IndexState` so the staleness gate can be exercised
    without a real git history behind the synthetic working tree."""

    def __init__(self, engine: Any, index: ContextIndex, lag_commits: int) -> None:
        super().__init__(engine)
        self._index = index
        self._lag_commits = lag_commits

    async def load_state(
        self, *, tenant_id: Any, project_id: Any, uow: Any = None
    ) -> IndexState:
        return IndexState(index=self._index, lag_commits=self._lag_commits)


@pytest.mark.asyncio
async def test_build_index_persists_index_and_current_chunks(tmp_path: Path) -> None:
    engine = new_engine()
    try:
        build_fake_repo(tmp_path)
        tenant = await seed_tenant(engine)
        service = ContextIndexService(engine, root=tmp_path)

        index = await service.build_index(
            tenant_id=tenant.tenant_id, project_id=tenant.project_id
        )

        assert index.status == "ACTIVE"
        assert index.embedding_model_version == EMBEDDING_MODEL_VERSION
        async with open_unit_of_work(
            engine, tenant_id=tenant.tenant_id, project_id=tenant.project_id
        ) as uow:
            repo = ContextIndexRepository()
            reloaded = await repo.get_index(
                uow.connection, tenant.tenant_id, tenant.project_id
            )
            chunks = await repo.list_current_chunks(
                uow.connection,
                tenant.tenant_id,
                tenant.project_id,
                index.current_version,
            )
            await uow.commit()
        assert reloaded == index
        assert chunks
        assert all(chunk.current for chunk in chunks)
        assert all(
            chunk.embedding_model_version == EMBEDDING_MODEL_VERSION for chunk in chunks
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reindex_incremental_tombstones_deleted_file(tmp_path: Path) -> None:
    engine = new_engine()
    try:
        build_fake_repo(tmp_path)
        tenant = await seed_tenant(engine)
        service = ContextIndexService(engine, root=tmp_path)
        index = await service.build_index(
            tenant_id=tenant.tenant_id, project_id=tenant.project_id
        )

        async with open_unit_of_work(
            engine, tenant_id=tenant.tenant_id, project_id=tenant.project_id
        ) as uow:
            before = await ContextIndexRepository().list_current_chunks(
                uow.connection,
                tenant.tenant_id,
                tenant.project_id,
                index.current_version,
            )
            await uow.commit()
        assert any(chunk.file_path == "AGENTS.md" for chunk in before)

        (tmp_path / "AGENTS.md").unlink()
        reindexed = await service.reindex_incremental(
            tenant_id=tenant.tenant_id, project_id=tenant.project_id
        )

        async with open_unit_of_work(
            engine, tenant_id=tenant.tenant_id, project_id=tenant.project_id
        ) as uow:
            after = await ContextIndexRepository().list_current_chunks(
                uow.connection,
                tenant.tenant_id,
                tenant.project_id,
                reindexed.current_version,
            )
            await uow.commit()
        assert reindexed.current_version == index.current_version
        assert not any(chunk.file_path == "AGENTS.md" for chunk in after)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reindex_incremental_idempotent_on_unchanged_repo(tmp_path: Path) -> None:
    engine = new_engine()
    try:
        build_fake_repo(tmp_path)
        tenant = await seed_tenant(engine)
        service = ContextIndexService(engine, root=tmp_path)
        index = await service.build_index(
            tenant_id=tenant.tenant_id, project_id=tenant.project_id
        )
        reindexed = await service.reindex_incremental(
            tenant_id=tenant.tenant_id, project_id=tenant.project_id
        )

        async with open_unit_of_work(
            engine, tenant_id=tenant.tenant_id, project_id=tenant.project_id
        ) as uow:
            chunks = await ContextIndexRepository().list_current_chunks(
                uow.connection,
                tenant.tenant_id,
                tenant.project_id,
                index.current_version,
            )
            await uow.commit()
        assert reindexed.current_version == index.current_version
        assert chunks
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_change_embedding_model_backfills_without_switching(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    try:
        build_fake_repo(tmp_path)
        tenant = await seed_tenant(engine)
        service = ContextIndexService(engine, root=tmp_path)
        index = await service.build_index(
            tenant_id=tenant.tenant_id, project_id=tenant.project_id
        )

        new_version = await service.change_embedding_model(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            model_version=_NEW_MODEL_VERSION,
        )

        assert new_version != index.current_version
        async with open_unit_of_work(
            engine, tenant_id=tenant.tenant_id, project_id=tenant.project_id
        ) as uow:
            repo = ContextIndexRepository()
            active = await repo.get_index(
                uow.connection, tenant.tenant_id, tenant.project_id
            )
            old_chunks = await repo.list_current_chunks(
                uow.connection,
                tenant.tenant_id,
                tenant.project_id,
                index.current_version,
            )
            new_chunks = await repo.list_current_chunks(
                uow.connection, tenant.tenant_id, tenant.project_id, new_version
            )
            await uow.commit()
        assert active is not None
        assert active.current_version == index.current_version  # NOT switched yet
        assert old_chunks and new_chunks
        assert all(
            chunk.embedding_model_version == _NEW_MODEL_VERSION for chunk in new_chunks
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_activate_index_switches_active_version(tmp_path: Path) -> None:
    engine = new_engine()
    try:
        build_fake_repo(tmp_path)
        tenant = await seed_tenant(engine)
        service = ContextIndexService(engine, root=tmp_path)
        await service.build_index(
            tenant_id=tenant.tenant_id, project_id=tenant.project_id
        )
        new_version = await service.change_embedding_model(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            model_version=_NEW_MODEL_VERSION,
        )

        activated = await service.activate_index(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            index_version=new_version,
        )

        assert activated.current_version == new_version
        assert activated.embedding_model_version == _NEW_MODEL_VERSION
        assert activated.status == "ACTIVE"
    finally:
        await engine.dispose()


def test_staleness_action_thresholds() -> None:
    assert staleness_action(0) == "ok"
    assert staleness_action(10) == "ok"
    assert staleness_action(11) == "warn"
    assert staleness_action(50) == "warn"
    assert staleness_action(51) == "block"


@pytest.mark.asyncio
async def test_semantic_retriever_returns_chunks_after_build(tmp_path: Path) -> None:
    engine = new_engine()
    try:
        build_fake_repo(tmp_path)
        tenant = await seed_tenant(engine)
        index = await ContextIndexService(engine, root=tmp_path).build_index(
            tenant_id=tenant.tenant_id, project_id=tenant.project_id
        )
        task = _task(tenant.tenant_id, tenant.project_id)

        async with open_unit_of_work(
            engine, tenant_id=tenant.tenant_id, project_id=tenant.project_id
        ) as uow:
            items = await semantic.retrieve(
                uow.connection,
                tenant_id=tenant.tenant_id,
                project_id=tenant.project_id,
                index_version=index.current_version,
                task=task,
                expected_write_scope=("engine/context",),
            )
            await uow.commit()

        assert items
        assert all(item.retriever == "semantic" for item in items)
        assert any("hashing.py" in (item.source_path or "") for item in items)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_compile_wires_semantic_retriever_when_index_present(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    try:
        build_fake_repo(tmp_path)
        fixture = await build_context_fixture(engine, mission_slug="MISSION-CTX-IDX")
        index_service = ContextIndexService(engine, root=tmp_path)
        await index_service.build_index(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        )
        service = ContextService(engine, root=tmp_path, index_service=index_service)

        compiled = await service.compile(task=fixture.task)

        assert not isinstance(compiled, ContextBudgetExceeded)
        assert "semantic" in compiled.retrievers_used
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_compile_blocks_when_index_stale(tmp_path: Path) -> None:
    engine = new_engine()
    try:
        build_fake_repo(tmp_path)
        fixture = await build_context_fixture(engine, mission_slug="MISSION-CTX-STALE")
        index = await ContextIndexService(engine, root=tmp_path).build_index(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        )
        stale_service = _FixedLagIndexService(engine, index, lag_commits=1000)
        service = ContextService(engine, root=tmp_path, index_service=stale_service)

        with pytest.raises(DdeError) as exc_info:
            await service.compile(task=fixture.task)

        assert exc_info.value.error_code == "CONTEXT_STALE"
    finally:
        await engine.dispose()
