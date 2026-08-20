"""`engine.workers` recovery (Chapter 19.1): a fresh session/engine reads
back the exact committed `WorkerRun`, its `WorkerEvent` stream, and the
`TaskAttempt` (`engine.missions`) it is bound to — matching what the
writing session produced."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from engine.context.repo import repo_root
from engine.missions.attempts import TaskAttemptRepository
from engine.truth.db import open_unit_of_work
from engine.workers.adapter import WorkerAction
from engine.workers.registry import WorkerProfileRegistry
from engine.workers.repository import WorkerEventRepository, WorkerRunRepository
from engine.workers.scripted_adapter import ScriptedWorkerAdapter
from engine.workers.service import WorkerManagerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.worker_fixtures import build_worker_fixture


@pytest.mark.asyncio
async def test_second_session_sees_committed_run_events_and_attempt(
    tmp_path: Path,
) -> None:
    root = repo_root()
    writer_engine = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            writer_engine, tmp_path, mission_slug="MISSION-WORKER-RECOVERY"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(writer_engine, root=root)
        registry = WorkerProfileRegistry()
        await registry.register_profile(ScriptedWorkerAdapter(workspaces))
        manager = WorkerManagerService(writer_engine, registry)

        action = WorkerAction(
            command=[sys.executable, "-c", "print('dde-worker-recovery-proof')"]
        )
        run = await manager.invoke_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=action,
            idempotency_key="worker-run-recovery-1",
        )
    finally:
        await writer_engine.dispose()  # simulate the writing process exiting

    reader_engine = new_engine()
    try:
        async with open_unit_of_work(
            reader_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            reloaded_run = await WorkerRunRepository().get_run(
                uow.connection, run.run_id
            )
            events = await WorkerEventRepository().list_for_run(
                uow.connection, run.run_id
            )
            attempt = await TaskAttemptRepository().get_attempt(
                uow.connection, run.task_attempt_id
            )
            await uow.commit()
        assert reloaded_run == run
        assert reloaded_run is not None and reloaded_run.status == "COMPLETED"
        assert [event.event_type for event in events] == [
            "WorkerRunCreated",
            "WorkerRunPreparing",
            "WorkerRunReady",
            "WorkerRunStarted",
            "WorkerRunCompleted",
        ]
        assert attempt is not None
        assert attempt.task_id == fixture.task.task_id
        assert attempt.attempt_id == run.task_attempt_id
    finally:
        if workspace is not None:
            await WorkspaceService(reader_engine, root=root).cleanup(
                workspace=workspace
            )
        await reader_engine.dispose()
