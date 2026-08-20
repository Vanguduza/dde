"""`engine.environments` recovery (Chapter 19.1): a fresh session/engine
reads back the exact committed `ExecutionEnvironment` a prior session
provisioned, including its real toolchain metadata."""

from __future__ import annotations

import pytest

from engine.environments.repository import ExecutionEnvironmentRepository
from engine.environments.service import ExecutionEnvironmentService
from engine.truth.db import open_unit_of_work
from tests.support.db import new_engine, seed_tenant


@pytest.mark.asyncio
async def test_second_session_sees_committed_environment() -> None:
    writer_engine = new_engine()
    tenant = await seed_tenant(writer_engine)
    service = ExecutionEnvironmentService(writer_engine)
    environment = await service.provision(
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        environment_class="development",
        resource_limits={"cpu_seconds": 60},
        network_policy={"mode": "unenforced"},
        filesystem_policy={"workspace_root_only": True},
    )
    await writer_engine.dispose()  # simulate the writing process exiting

    reader_engine = new_engine()
    try:
        async with open_unit_of_work(
            reader_engine, tenant_id=tenant.tenant_id, project_id=tenant.project_id
        ) as uow:
            reloaded = await ExecutionEnvironmentRepository().get_environment(
                uow.connection, environment.environment_id
            )
            await uow.commit()
        assert reloaded == environment
        assert reloaded is not None
        assert reloaded.toolchain_manifest == environment.toolchain_manifest
    finally:
        await reader_engine.dispose()
