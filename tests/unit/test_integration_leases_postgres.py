"""PostgreSQL-backed `WriteScopeLease`: schema, state-transition, negative
and recovery tests (Chapter 19.1). Exercises `engine.integration.service.
WriteScopeLeaseService` -- the production writer of `write_scope_leases`
(Chapter 3.8) -- and its wiring into `engine.execution.service.
ExecutionPlanService.plan()` (`ExecutionPlan.write_scope_lease_id`,
DDE-013's mandate), against a real database and real, persisted
`Task`/`Mission` rows."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.core.errors import DdeError
from engine.execution.service import ExecutionPlanService
from engine.integration.service import WriteScopeLeaseService
from tests.support.db import new_engine
from tests.support.execution_fixtures import build_execution_fixture
from tests.support.integration_fixtures import build_shared_mission_tasks


@pytest.mark.asyncio
async def test_execution_plan_acquires_and_reuses_a_real_write_scope_lease(
    tmp_path: Path,
) -> None:
    """DDE-013's mandate: `ExecutionPlanService.plan()` (DDE-010) now
    populates the real `write_scope_lease_id` field it used to leave
    `None`. A schema-round-trip and idempotency test in one: the persisted
    lease's fields mirror the task's real declared scope, and re-planning
    the same task reuses the same lease rather than acquiring a second,
    self-conflicting one."""
    engine = new_engine()
    try:
        fixture = await build_execution_fixture(
            engine,
            tmp_path,
            mission_slug="MISSION-LEASE-PLAN",
            task_class="verification",
        )
        plan_service = ExecutionPlanService(engine)
        plan = await plan_service.plan(
            task=fixture.task,
            route_decision=fixture.route_decision,
            context_package_id=fixture.context_package.package_id,
        )
        assert plan.write_scope_lease_id is not None

        leases = WriteScopeLeaseService(engine)
        lease = await leases.get_lease(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            lease_id=plan.write_scope_lease_id,
        )
        assert lease.task_id == fixture.task.task_id
        assert lease.mission_id == fixture.task.mission_id
        assert lease.scope_patterns == fixture.task.expected_write_scope
        assert lease.exclusive is True
        assert lease.status == "RESERVED"
        assert lease.released_at is None
        assert lease.expires_at > lease.acquired_at

        again = await plan_service.plan(
            task=fixture.task,
            route_decision=fixture.route_decision,
            context_package_id=fixture.context_package.package_id,
        )
        assert again.write_scope_lease_id == plan.write_scope_lease_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_lease_lifecycle_transitions_and_illegal_transition_is_rejected(
    tmp_path: Path,
) -> None:
    """Chapter 10.3's real states: `RESERVED -> ACTIVE -> RELEASED`. A
    transition out of a terminal state (`RELEASED -> ACTIVE`) is refused as
    a typed error, never silently applied."""
    engine = new_engine()
    try:
        fixture = await build_execution_fixture(
            engine,
            tmp_path,
            mission_slug="MISSION-LEASE-LIFECYCLE",
            task_class="verification",
        )
        plan_service = ExecutionPlanService(engine)
        plan = await plan_service.plan(
            task=fixture.task,
            route_decision=fixture.route_decision,
            context_package_id=fixture.context_package.package_id,
        )
        assert plan.write_scope_lease_id is not None
        leases = WriteScopeLeaseService(engine)
        lease = await leases.get_lease(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            lease_id=plan.write_scope_lease_id,
        )
        assert lease.status == "RESERVED"

        active = await leases.activate(lease=lease)
        assert active.status == "ACTIVE"

        released = await leases.release(lease=active, target_status="RELEASED")
        assert released.status == "RELEASED"
        assert released.released_at is not None

        with pytest.raises(DdeError) as excinfo:
            await leases.activate(lease=released)
        assert excinfo.value.error_code == "VERSION_CONFLICT"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_overlapping_exclusive_scope_within_same_project_is_refused(
    tmp_path: Path,
) -> None:
    """Chapter 10.3's conflict rule, proven with a real, unmocked overlap:
    two tasks in the same project/mission declaring the identical write
    scope cannot both hold a `RESERVED`/`ACTIVE` lease over it at once.
    Releasing the first frees the scope for the second -- the rule checks
    what is genuinely *held*, not history."""
    engine = new_engine()
    try:
        shared = await build_shared_mission_tasks(
            engine,
            tmp_path,
            mission_slug="MISSION-LEASE-CONFLICT",
            scope=["tests/fixtures/dde013-lease-conflict"],
        )
        leases = WriteScopeLeaseService(engine)
        first = await leases.acquire(
            tenant_id=shared.tenant.tenant_id,
            project_id=shared.tenant.project_id,
            mission_id=shared.mission.mission_id,
            task_id=shared.task_a.task_id,
            scope_patterns=list(shared.task_a.expected_write_scope),
        )
        assert first.status == "RESERVED"

        with pytest.raises(DdeError) as excinfo:
            await leases.acquire(
                tenant_id=shared.tenant.tenant_id,
                project_id=shared.tenant.project_id,
                mission_id=shared.mission.mission_id,
                task_id=shared.task_b.task_id,
                scope_patterns=list(shared.task_b.expected_write_scope),
            )
        assert excinfo.value.error_code == "WRITE_SCOPE_CONFLICT"
        assert excinfo.value.details is not None
        assert excinfo.value.details["conflicting_task_id"] == str(
            shared.task_a.task_id
        )

        released = await leases.release(lease=first)
        assert released.status == "RELEASED"

        second = await leases.acquire(
            tenant_id=shared.tenant.tenant_id,
            project_id=shared.tenant.project_id,
            mission_id=shared.mission.mission_id,
            task_id=shared.task_b.task_id,
            scope_patterns=list(shared.task_b.expected_write_scope),
        )
        assert second.status == "RESERVED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_second_session_sees_the_exact_committed_lease(tmp_path: Path) -> None:
    """Chapter 19.1's recovery test type: a lease committed by one session
    (engine/connection pool) is read back identically by a fresh one."""
    writer_engine = new_engine()
    fixture = await build_execution_fixture(
        writer_engine,
        tmp_path,
        mission_slug="MISSION-LEASE-RECOVERY",
        task_class="verification",
    )
    plan_service = ExecutionPlanService(writer_engine)
    plan = await plan_service.plan(
        task=fixture.task,
        route_decision=fixture.route_decision,
        context_package_id=fixture.context_package.package_id,
    )
    assert plan.write_scope_lease_id is not None
    await writer_engine.dispose()

    reader_engine = new_engine()
    try:
        leases = WriteScopeLeaseService(reader_engine)
        lease = await leases.get_lease(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            lease_id=plan.write_scope_lease_id,
        )
        assert lease.task_id == fixture.task.task_id
        assert lease.mission_id == fixture.task.mission_id
        assert lease.status == "RESERVED"
        assert lease.scope_patterns == fixture.task.expected_write_scope
    finally:
        await reader_engine.dispose()
