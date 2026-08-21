"""`engine.context` index recovery (Chapter 19.1): a fresh session/engine
must see a committed semantic index and its current chunks exactly as built
— not merely held in the writer's in-process objects.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.context.index_repository import ContextIndexRepository
from engine.context.index_service import ContextIndexService
from engine.truth.db import open_unit_of_work
from tests.support.context_fixtures import build_fake_repo
from tests.support.db import new_engine, seed_tenant


@pytest.mark.asyncio
async def test_second_session_sees_committed_index_and_chunks(tmp_path: Path) -> None:
    build_fake_repo(tmp_path)
    writer_engine = new_engine()
    tenant = await seed_tenant(writer_engine)
    index = await ContextIndexService(writer_engine, root=tmp_path).build_index(
        tenant_id=tenant.tenant_id, project_id=tenant.project_id
    )
    await writer_engine.dispose()  # simulate the writing process exiting

    reader_engine = new_engine()
    try:
        async with open_unit_of_work(
            reader_engine, tenant_id=tenant.tenant_id, project_id=tenant.project_id
        ) as uow:
            repo = ContextIndexRepository()
            reread = await repo.get_index(
                uow.connection, tenant.tenant_id, tenant.project_id
            )
            chunks = await repo.list_current_chunks(
                uow.connection,
                tenant.tenant_id,
                tenant.project_id,
                index.current_version,
            )
            await uow.commit()
        assert reread is not None
        assert reread.current_version == index.current_version
        assert reread.embedding_model_version == index.embedding_model_version
        assert chunks
        assert all(chunk.current for chunk in chunks)
        assert all(chunk.embedding for chunk in chunks)
    finally:
        await reader_engine.dispose()
