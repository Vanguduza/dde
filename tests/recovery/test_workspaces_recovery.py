"""`engine.workspaces` recovery (Chapter 19.1): a fresh session/engine must
see a committed `Workspace`'s final `status` and a prior `execute()` call's
exact captured output — not merely held in the writer's in-process objects.
"""

from __future__ import annotations

import sys

import pytest

from engine.context.repo import repo_root
from engine.events.repository import EventsRepository
from engine.truth.db import open_unit_of_work
from engine.workspaces.repository import WorkspaceRepository
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine, seed_tenant


@pytest.mark.asyncio
async def test_second_session_sees_committed_workspace_and_command_output() -> None:
    writer_engine = new_engine()
    root = repo_root()
    writer_service = WorkspaceService(writer_engine, root=root)
    tenant = await seed_tenant(writer_engine)
    workspace = await writer_service.create(
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        mission_id=None,
        task_id=None,
        execution_environment_id=None,
        base_revision="HEAD",
        policy={},
    )
    result = await writer_service.execute(
        workspace=workspace,
        command=[sys.executable, "-c", "print('dde-recovery-proof')"],
    )
    await writer_service.cleanup(workspace=workspace)
    await writer_engine.dispose()  # simulate the writing process exiting

    reader_engine = new_engine()
    try:
        async with open_unit_of_work(
            reader_engine, tenant_id=tenant.tenant_id, project_id=tenant.project_id
        ) as uow:
            events = await EventsRepository().list_events_for_aggregate(
                uow.connection, "workspace", workspace.workspace_id
            )
            reloaded_workspace = await WorkspaceRepository().get_workspace(
                uow.connection, workspace.workspace_id
            )
            await uow.commit()
        executed = [e for e in events if e.event_type == "WorkspaceCommandExecuted"]
        assert len(executed) == 1
        assert executed[0].payload["exit_code"] == result.exit_code
        assert executed[0].payload["stdout"] == result.stdout
        assert reloaded_workspace is not None
        assert reloaded_workspace.status == "CLEANED_UP"
    finally:
        await reader_engine.dispose()
