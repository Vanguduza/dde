"""Mission Kernel recovery and concurrency (Chapter 19.1, 3.5): a mission's
row update and its `MissionTransitioned` event share one PostgreSQL
transaction, so a failure appending the event rolls back the status change
too.

TaskGraph-spanning recovery coverage (fresh-process durability across
`missions`/`task_graphs`/`tasks`/`task_graph_edges`, and the cross-module
atomic-rollback test proving `engine.missions` and `engine.planning` commit
or roll back together) now lives in `tests/recovery/test_planning_recovery.py`.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from engine.contracts.mission import Mission
from engine.core.errors import DdeError
from engine.events.service import EventService
from engine.missions.service import MissionService
from tests.support.db import new_engine, seed_tenant

REQUIREMENT_SLUG = "REQ-RECOVERY"


class _FailingEventService(EventService):
    """Simulates a crash while appending the domain event, after the
    mission status update has already executed in the same open
    transaction."""

    async def append(self, **kwargs: Any) -> None:  # type: ignore[override]
        raise DdeError("POLICY_DENIED", "forced event failure for recovery test")


async def _create_mission(service: MissionService, fixture, *, slug: str) -> Mission:
    return await service.create_mission(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        slug=slug,
        title="Health endpoint",
        intent="Add a /health endpoint",
        success_definition="healthz returns ok",
        scope=["engine", "schemas", "tests"],
        requirement_refs=[REQUIREMENT_SLUG],
        autonomy_ceiling=3,
    )


@pytest.mark.asyncio
async def test_event_failure_rolls_back_mission_transition() -> None:
    """`transition_mission` writes the mission row and appends
    `MissionTransitioned` in one transaction (Chapter 3.8's "Event ...
    Owning aggregate transaction" rule): if the event append fails, the
    mission status change never commits either."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = MissionService(engine, EventService(engine))
        created = await _create_mission(service, fixture, slug="MISSION-ATOMIC-001")

        failing_service = MissionService(engine, _FailingEventService(engine))
        with pytest.raises(DdeError):
            await failing_service.transition_mission(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                mission_id=created.mission_id,
                target_status="ACTIVE",
                lock_version=created.lock_version,
            )

        reread = await service.get_mission(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=created.mission_id,
        )
        assert reread.status == "CREATED"
        assert reread.lock_version == created.lock_version
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_mission_transition_has_exactly_one_winner() -> None:
    """Chapter 3.5's stated purpose for `lock_version`: two simultaneous
    writers starting from the same `lock_version` must produce exactly one
    successful write and one rejected `VERSION_CONFLICT`."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = MissionService(engine, EventService(engine))
        created = await _create_mission(service, fixture, slug="MISSION-RACE-001")
        active = await service.transition_mission(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=created.mission_id,
            target_status="ACTIVE",
            lock_version=created.lock_version,
        )

        async def _attempt(target_status: str) -> Mission:
            return await service.transition_mission(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                mission_id=created.mission_id,
                target_status=target_status,
                lock_version=active.lock_version,
            )

        results = await asyncio.gather(
            _attempt("PARTIAL"), _attempt("PAUSED"), return_exceptions=True
        )
        successes = [item for item in results if isinstance(item, Mission)]
        failures = [item for item in results if isinstance(item, DdeError)]
        others = [
            item
            for item in results
            if not isinstance(item, (Mission, DdeError))  # noqa: UP038
        ]
        assert others == []
        assert len(successes) == 1
        assert len(failures) == 1
        assert failures[0].error_code == "VERSION_CONFLICT"
        assert failures[0].retryable is True

        final = await service.get_mission(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=created.mission_id,
        )
        assert final.status == successes[0].status
        assert final.lock_version == active.lock_version + 1
    finally:
        await engine.dispose()
