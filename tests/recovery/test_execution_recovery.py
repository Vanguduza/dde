"""`engine.execution` recovery (Chapter 19.1): a fresh session/engine reads
back the exact committed `ExecutionPlan` and its `ExecutionPlanCommitted`
event, matching what the planning session produced."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.events.repository import EventsRepository
from engine.execution.repository import ExecutionPlanRepository
from engine.execution.service import ExecutionPlanService
from engine.truth.db import open_unit_of_work
from tests.support.db import new_engine
from tests.support.execution_fixtures import build_execution_fixture


@pytest.mark.asyncio
async def test_second_session_sees_committed_plan_and_events(tmp_path: Path) -> None:
    writer_engine = new_engine()
    plan_service = ExecutionPlanService(writer_engine)
    fixture = await build_execution_fixture(
        writer_engine, tmp_path, mission_slug="MISSION-EXEC-RECOVERY"
    )
    plan = await plan_service.plan(
        task=fixture.task,
        route_decision=fixture.route_decision,
        context_package_id=fixture.context_package.package_id,
    )
    await writer_engine.dispose()  # simulate the writing process exiting

    reader_engine = new_engine()
    try:
        async with open_unit_of_work(
            reader_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            reloaded = await ExecutionPlanRepository().get_plan(
                uow.connection, plan.plan_id
            )
            events = await EventsRepository().list_events_for_aggregate(
                uow.connection, "execution_plan", plan.plan_id
            )
            await uow.commit()
        assert reloaded == plan
        committed = [e for e in events if e.event_type == "ExecutionPlanCommitted"]
        assert len(committed) == 1
        assert committed[0].payload["plan_hash"] == plan.plan_hash
    finally:
        await reader_engine.dispose()
