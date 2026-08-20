"""PostgreSQL-backed `engine.missions.attempts` (Chapter 19.1): schema round
trip plus `task_attempts.sequence`'s real per-task ordinality — the
prerequisite `engine.workers.service.WorkerManagerService` depends on for
every `WorkerRun` it creates."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.core.errors import DdeError
from engine.execution.service import ExecutionPlanService
from engine.missions.attempts import TaskAttemptService
from engine.truth.db import open_unit_of_work
from tests.support.db import new_engine
from tests.support.execution_fixtures import build_execution_fixture


@pytest.mark.asyncio
async def test_create_assigns_sequence_and_rejects_mismatched_plan(
    tmp_path: Path,
) -> None:
    db_engine = new_engine()
    try:
        fixture = await build_execution_fixture(
            db_engine, tmp_path, mission_slug="MISSION-ATTEMPTS-SEQUENCE"
        )
        service = TaskAttemptService(db_engine)

        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            plan_service = ExecutionPlanService(db_engine)
            plan = await plan_service.plan(
                task=fixture.task,
                route_decision=fixture.route_decision,
                context_package_id=fixture.context_package.package_id,
                uow=uow,
            )
            first = await service.create(
                task=fixture.task,
                execution_plan=plan,
                workspace_revision="deadbeef",
                input_context_hash=fixture.context_package.assembly_hash,
                uow=uow,
            )
            second = await service.create(
                task=fixture.task,
                execution_plan=plan,
                workspace_revision="deadbeef",
                input_context_hash=fixture.context_package.assembly_hash,
                uow=uow,
            )
            await uow.commit()

        assert first.sequence == 1
        assert second.sequence == 2
        assert first.attempt_id != second.attempt_id

        reloaded = await service.get_attempt(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            attempt_id=first.attempt_id,
        )
        assert reloaded == first

        other_fixture = await build_execution_fixture(
            db_engine, tmp_path, mission_slug="MISSION-ATTEMPTS-MISMATCH"
        )
        with pytest.raises(DdeError) as excinfo:
            await service.create(
                task=other_fixture.task,
                execution_plan=plan,
                workspace_revision="deadbeef",
                input_context_hash=other_fixture.context_package.assembly_hash,
            )
        assert excinfo.value.error_code == "POLICY_DENIED"
    finally:
        await db_engine.dispose()
