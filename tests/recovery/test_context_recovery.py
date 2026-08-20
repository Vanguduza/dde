"""`engine.context` recovery (Chapter 19.1): a fresh session/engine must
see a committed `ContextPackage`'s coverage and `assembly_hash` exactly
as compiled — not merely held in the writer's in-process objects.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.context.model import ContextBudgetExceeded
from engine.context.repository import ContextRepository
from engine.context.service import ContextService
from engine.truth.db import open_unit_of_work
from tests.support.context_fixtures import build_context_fixture, build_fake_repo
from tests.support.db import new_engine


@pytest.mark.asyncio
async def test_second_session_sees_committed_context_package(tmp_path: Path) -> None:
    build_fake_repo(tmp_path)
    writer_engine = new_engine()
    fixture = await build_context_fixture(
        writer_engine, mission_slug="MISSION-CTX-RECOVERY"
    )
    service = ContextService(writer_engine, root=tmp_path)
    compiled = await service.compile(task=fixture.task)
    assert not isinstance(compiled, ContextBudgetExceeded)
    await writer_engine.dispose()  # simulate the writing process exiting

    reader_engine = new_engine()
    try:
        async with open_unit_of_work(
            reader_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            reread = await ContextRepository().get_context_package(
                uow.connection, compiled.package_id
            )
            await uow.commit()
        assert reread is not None
        assert reread.coverage == compiled.coverage
        assert reread.assembly_hash == compiled.assembly_hash
        assert reread.status == compiled.status
        assert reread.version == compiled.version
        assert reread.retrievers_used == compiled.retrievers_used
    finally:
        await reader_engine.dispose()
