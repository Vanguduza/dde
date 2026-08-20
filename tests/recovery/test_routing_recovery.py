"""`engine.routing` recovery (Chapter 19.1): a fresh session/engine must
see a committed `RouteDecision`'s candidates, selection and hash exactly
as computed — not merely held in the writer's in-process objects.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.routing.repository import RouteDecisionRepository
from engine.routing.service import RouterService
from engine.truth.db import open_unit_of_work
from tests.support.db import new_engine
from tests.support.routing_fixtures import build_routing_fixture


@pytest.mark.asyncio
async def test_second_session_sees_committed_route_decision(tmp_path: Path) -> None:
    writer_engine = new_engine()
    fixture = await build_routing_fixture(
        writer_engine, tmp_path, mission_slug="MISSION-ROUTE-RECOVERY"
    )
    service = RouterService(writer_engine)
    decision = await service.route(task=fixture.task)
    await writer_engine.dispose()  # simulate the writing process exiting

    reader_engine = new_engine()
    try:
        async with open_unit_of_work(
            reader_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            reread = await RouteDecisionRepository().get_route_decision(
                uow.connection, decision.decision_id
            )
            await uow.commit()
        assert reread is not None
        assert reread.candidates == decision.candidates
        assert reread.selected_worker_profile_id == decision.selected_worker_profile_id
        assert reread.workload_class == decision.workload_class
        assert reread.decision_hash == decision.decision_hash
        assert reread.reason_codes == decision.reason_codes
        assert reread.fallback_plan == decision.fallback_plan
        assert reread.escalation_plan == decision.escalation_plan
    finally:
        await reader_engine.dispose()
