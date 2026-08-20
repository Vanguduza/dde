"""PostgreSQL-backed `engine.capabilities.lease_service`: schema,
state-transition, negative and recovery tests (Chapter 19.1) -- DDE-017's
`CapabilityLease` acceptance proof, exercised directly against
`CapabilityLeaseService` (the sole writer of `capability_leases`, Chapter
3.8) rather than through a full worker run. `tests/unit/
test_capability_lease_enforcement.py` covers the same lease lifecycle as
observed through the real `ScriptedWorkerAdapter`/`WorkspaceService`
enforcement call sites.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from engine.capabilities.lease_service import CapabilityLeaseService
from engine.capabilities.seed import seed_capabilities
from engine.capabilities.service import CapabilityRegistryService
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.execution.service import ExecutionPlanService
from tests.support.db import new_engine
from tests.support.execution_fixtures import build_execution_fixture


async def _planned_fixture(engine, tmp_path: Path, *, mission_slug: str):
    execution_fixture = await build_execution_fixture(
        engine, tmp_path, mission_slug=mission_slug, task_class="verification"
    )
    await seed_capabilities(
        CapabilityRegistryService(engine),
        tenant_id=execution_fixture.tenant.tenant_id,
        project_id=execution_fixture.tenant.project_id,
    )
    plan = await ExecutionPlanService(engine).plan(
        task=execution_fixture.task,
        route_decision=execution_fixture.route_decision,
        context_package_id=execution_fixture.context_package.package_id,
    )
    return execution_fixture, plan


@pytest.mark.asyncio
async def test_schema_round_trip_persists_declared_columns(tmp_path: Path) -> None:
    """A row read back from the real `capability_leases` table validates
    against the JSON-schema-generated contract with no drift (Chapter
    3.1) -- the schema test."""
    engine = new_engine()
    try:
        fixture, plan = await _planned_fixture(
            engine, tmp_path, mission_slug="MISSION-LEASE-SCHEMA"
        )
        leases = CapabilityLeaseService(engine)
        worker_run_id = uuid7()
        granted = await leases.request(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.mission.mission_id,
            task_id=fixture.task.task_id,
            execution_plan_id=plan.plan_id,
            worker_run_id=worker_run_id,
            capability_id="capability.run_local_process",
            capability_version="1",
            requested_by="system:test",
            idempotency_key=f"{worker_run_id}:capability.run_local_process",
        )
        assert granted.status == "GRANTED"
        assert granted.revocable is True
        assert granted.lease_hash

        reloaded = await leases.get_lease(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            lease_id=granted.lease_id,
        )
        assert reloaded == granted
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_requesting_the_same_lease_twice_is_idempotent(tmp_path: Path) -> None:
    engine = new_engine()
    try:
        fixture, plan = await _planned_fixture(
            engine, tmp_path, mission_slug="MISSION-LEASE-IDEMPOTENT"
        )
        leases = CapabilityLeaseService(engine)
        worker_run_id = uuid7()
        kwargs = dict(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.mission.mission_id,
            task_id=fixture.task.task_id,
            execution_plan_id=plan.plan_id,
            worker_run_id=worker_run_id,
            capability_id="capability.run_local_process",
            capability_version="1",
            requested_by="system:test",
            idempotency_key=f"{worker_run_id}:capability.run_local_process",
        )
        first = await leases.request(**kwargs)
        second = await leases.request(**kwargs)
        assert second.lease_id == first.lease_id
        assert second.status == first.status == "GRANTED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_request_against_a_nonexistent_capability_is_denied(
    tmp_path: Path,
) -> None:
    """Chapter 9.2's real grant decision: no `ACTIVE` descriptor at all
    means denial, not an exception -- "lease denial is a normal control
    outcome, not an error"."""
    engine = new_engine()
    try:
        fixture, plan = await _planned_fixture(
            engine, tmp_path, mission_slug="MISSION-LEASE-NEG-MISSING"
        )
        leases = CapabilityLeaseService(engine)
        worker_run_id = uuid7()
        denied = await leases.request(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.mission.mission_id,
            task_id=fixture.task.task_id,
            execution_plan_id=plan.plan_id,
            worker_run_id=worker_run_id,
            capability_id="capability.does-not-exist",
            capability_version="1",
            requested_by="system:test",
            idempotency_key=f"{worker_run_id}:capability.does-not-exist",
        )
        assert denied.status == "DENIED"
        assert denied.denied_reason is not None
        assert "no ACTIVE capability descriptor" in denied.denied_reason
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_request_against_a_retired_descriptor_is_denied(
    tmp_path: Path,
) -> None:
    """A real, previously-`CERTIFIED` descriptor that has since been
    retired (Chapter 9.1's `ACTIVE -> RETIRED`) must deny a new lease
    request -- proving the grant decision reads live lifecycle_status, not
    a cached/point-in-time snapshot."""
    engine = new_engine()
    try:
        fixture, plan = await _planned_fixture(
            engine, tmp_path, mission_slug="MISSION-LEASE-NEG-RETIRED"
        )
        registry = CapabilityRegistryService(engine)
        capability_id = f"capability.retired-for-lease-test-{uuid4().hex}"
        descriptor = await registry.register(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            capability_id=capability_id,
            version="1",
            category="process",
            summary="Retired before a lease is requested against it.",
            side_effect_class="WORKSPACE_LOCAL",
            risk_class="low",
            enforcement_tier="T1",
            registered_by="system:test",
            certification_status="CERTIFIED",
        )
        await registry.retire(
            descriptor=descriptor,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        )

        leases = CapabilityLeaseService(engine)
        worker_run_id = uuid7()
        denied = await leases.request(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.mission.mission_id,
            task_id=fixture.task.task_id,
            execution_plan_id=plan.plan_id,
            worker_run_id=worker_run_id,
            capability_id=capability_id,
            capability_version="1",
            requested_by="system:test",
            idempotency_key=f"{worker_run_id}:{capability_id}",
        )
        assert denied.status == "DENIED"
        assert denied.denied_reason is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_state_transition_require_active_moves_granted_to_active(
    tmp_path: Path,
) -> None:
    """Chapter 9.2's real lifecycle: `GRANTED -> ACTIVE` happens on the
    first successful `require_active` check, not at grant time."""
    engine = new_engine()
    try:
        fixture, plan = await _planned_fixture(
            engine, tmp_path, mission_slug="MISSION-LEASE-STATE"
        )
        leases = CapabilityLeaseService(engine)
        worker_run_id = uuid7()
        granted = await leases.request(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.mission.mission_id,
            task_id=fixture.task.task_id,
            execution_plan_id=plan.plan_id,
            worker_run_id=worker_run_id,
            capability_id="capability.run_local_process",
            capability_version="1",
            requested_by="system:test",
            idempotency_key=f"{worker_run_id}:capability.run_local_process",
        )
        assert granted.status == "GRANTED"

        active = await leases.require_active(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            worker_run_id=worker_run_id,
            capability_id="capability.run_local_process",
        )
        assert active.lease_id == granted.lease_id
        assert active.status == "ACTIVE"

        # A second check against the same, still-held lease is a no-op
        # transition-wise -- it stays ACTIVE, never re-fires the GRANTED
        # -> ACTIVE event.
        again = await leases.require_active(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            worker_run_id=worker_run_id,
            capability_id="capability.run_local_process",
        )
        assert again.status == "ACTIVE"

        consumed = await leases.consume_all_for_run(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            worker_run_id=worker_run_id,
        )
        assert [item.lease_id for item in consumed] == [granted.lease_id]
        assert consumed[0].status == "CONSUMED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_require_active_without_any_lease_is_denied(
    tmp_path: Path,
) -> None:
    """Chapter 7.2's T1 brokered enforcement guard, at the lease-service
    level: no lease was ever requested for this run/capability -- fails
    closed rather than allowing the caller through."""
    engine = new_engine()
    try:
        fixture, _plan = await _planned_fixture(
            engine, tmp_path, mission_slug="MISSION-LEASE-NEG-NO-LEASE"
        )
        leases = CapabilityLeaseService(engine)
        with pytest.raises(DdeError) as excinfo:
            await leases.require_active(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                worker_run_id=uuid7(),
                capability_id="capability.run_local_process",
            )
        assert excinfo.value.error_code == "POLICY_DENIED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_revoked_mid_run_fails_closed_at_the_next_gated_check(
    tmp_path: Path,
) -> None:
    """AGENTS.md/Chapter 18.2's S2 exit-gate scenario: a lease revoked
    while a "run" is conceptually in progress must fail the NEXT
    capability-gated check closed. Proven with a real concurrent
    revocation racing a simulated long-running operation -- this mission's
    real, achievable granularity ("next discrete check", not per-syscall
    interception; see `engine.capabilities.lease_service`'s module
    docstring)."""
    engine = new_engine()
    try:
        fixture, plan = await _planned_fixture(
            engine, tmp_path, mission_slug="MISSION-LEASE-REVOKE-MIDRUN"
        )
        leases = CapabilityLeaseService(engine)
        worker_run_id = uuid7()
        await leases.request(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.mission.mission_id,
            task_id=fixture.task.task_id,
            execution_plan_id=plan.plan_id,
            worker_run_id=worker_run_id,
            capability_id="capability.run_local_process",
            capability_version="1",
            requested_by="system:test",
            idempotency_key=f"{worker_run_id}:capability.run_local_process",
        )
        first_check = await leases.require_active(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            worker_run_id=worker_run_id,
            capability_id="capability.run_local_process",
        )
        assert first_check.status == "ACTIVE"

        async def simulated_long_running_operation() -> str:
            await asyncio.sleep(0.2)
            return "operation finished"

        async def concurrent_revocation():
            await asyncio.sleep(0.05)
            return await leases.revoke(
                lease=first_check, reason="operator revoked mid-run"
            )

        operation_result, revoked = await asyncio.gather(
            simulated_long_running_operation(), concurrent_revocation()
        )
        assert operation_result == "operation finished"
        assert revoked.status == "REVOKED"
        assert revoked.revocation_reason == "operator revoked mid-run"

        with pytest.raises(DdeError) as excinfo:
            await leases.require_active(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                worker_run_id=worker_run_id,
                capability_id="capability.run_local_process",
            )
        assert excinfo.value.error_code == "POLICY_DENIED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_expired_lease_fails_closed_and_is_marked_expired(
    tmp_path: Path,
) -> None:
    """Chapter 9.2: "expired ... leases fail closed at the enforcement
    boundary" -- and the expiry itself becomes a real, durable transition,
    not merely an inferred one."""
    engine = new_engine()
    try:
        fixture, plan = await _planned_fixture(
            engine, tmp_path, mission_slug="MISSION-LEASE-EXPIRED"
        )
        leases = CapabilityLeaseService(engine)
        worker_run_id = uuid7()
        granted = await leases.request(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.mission.mission_id,
            task_id=fixture.task.task_id,
            execution_plan_id=plan.plan_id,
            worker_run_id=worker_run_id,
            capability_id="capability.run_local_process",
            capability_version="1",
            requested_by="system:test",
            idempotency_key=f"{worker_run_id}:capability.run_local_process",
            ttl=timedelta(seconds=-1),
        )
        assert granted.status == "GRANTED"

        with pytest.raises(DdeError) as excinfo:
            await leases.require_active(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                worker_run_id=worker_run_id,
                capability_id="capability.run_local_process",
            )
        assert excinfo.value.error_code == "POLICY_DENIED"

        reloaded = await leases.get_lease(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            lease_id=granted.lease_id,
        )
        assert reloaded.status == "EXPIRED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_second_session_sees_the_exact_committed_lease(tmp_path: Path) -> None:
    """Chapter 19.1's recovery test type: a lease committed by one session
    (engine/connection pool) is read back identically by a fresh one."""
    writer_engine = new_engine()
    fixture, plan = await _planned_fixture(
        writer_engine, tmp_path, mission_slug="MISSION-LEASE-RECOVERY"
    )
    leases = CapabilityLeaseService(writer_engine)
    worker_run_id = uuid7()
    granted = await leases.request(
        tenant_id=fixture.tenant.tenant_id,
        project_id=fixture.tenant.project_id,
        mission_id=fixture.mission.mission_id,
        task_id=fixture.task.task_id,
        execution_plan_id=plan.plan_id,
        worker_run_id=worker_run_id,
        capability_id="capability.run_local_process",
        capability_version="1",
        requested_by="system:test",
        idempotency_key=f"{worker_run_id}:capability.run_local_process",
    )
    await writer_engine.dispose()

    reader_engine = new_engine()
    try:
        reader_leases = CapabilityLeaseService(reader_engine)
        reloaded = await reader_leases.get_lease(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            lease_id=granted.lease_id,
        )
        assert reloaded == granted
    finally:
        await reader_engine.dispose()
