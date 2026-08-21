"""PostgreSQL-backed `engine.routing`: schema and negative tests (Chapter
19.1). Exercises `engine.routing.service.RouterService`, the production
writer of `route_decisions` (Chapter 3.8), against a real database and a
real, persisted Task + compiled ContextPackage (Chapter 2.5's spine).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.routing.policy import (
    HUMAN_DECISION_TASK,
    POLICY_VERSION,
    PROFILE_LONGCONTEXT_ECONOMY,
    PROFILE_PREMIUM_REASONING,
)
from engine.routing.repository import RouteDecisionRepository
from engine.routing.service import RouterService
from engine.truth.db import open_unit_of_work
from tests.support.db import new_engine
from tests.support.routing_fixtures import build_routing_fixture


@pytest.mark.asyncio
async def test_schema_round_trip_persists_declared_columns(tmp_path: Path) -> None:
    """A `route_decisions` row read back from the real table validates
    against the JSON-schema-generated contract with no drift (Chapter
    3.1) — the schema test."""
    engine = new_engine()
    try:
        fixture = await build_routing_fixture(
            engine, tmp_path, mission_slug="MISSION-ROUTE-SCHEMA"
        )
        service = RouterService(engine)

        decision = await service.route(task=fixture.task)

        assert decision.tenant_id == fixture.tenant.tenant_id
        assert decision.project_id == fixture.tenant.project_id
        assert decision.mission_id == fixture.mission.mission_id
        assert decision.task_id == fixture.task.task_id
        assert decision.policy_version == POLICY_VERSION
        assert decision.selection_source == "deterministic"
        assert decision.selection_propensity == 1.0
        assert decision.decision_hash

        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            reloaded = await RouteDecisionRepository().get_route_decision(
                uow.connection, decision.decision_id
            )
            await uow.commit()
        assert reloaded == decision
        assert reloaded is not None
        assert len(reloaded.candidates) == 5
        for candidate in reloaded.candidates:
            assert set(candidate) == {
                "profile_id",
                "gate_results",
                "eliminated_at_gate",
                "scores",
            }
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_two_genuinely_different_tasks_route_to_two_different_profiles(
    tmp_path: Path,
) -> None:
    """The acceptance proof against real persisted state: a low-risk
    implementation task and a high-risk implementation task are two real,
    independently persisted `Task` rows that route to two different real,
    persisted `RouteDecision` outcomes — not a single hardcoded branch."""
    engine = new_engine()
    try:
        low_risk = await build_routing_fixture(
            engine,
            tmp_path,
            mission_slug="MISSION-ROUTE-LOW",
            task_class="implementation",
            risk_class="low",
        )
        high_risk = await build_routing_fixture(
            engine,
            tmp_path,
            mission_slug="MISSION-ROUTE-HIGH",
            task_class="implementation",
            risk_class="high",
        )
        service = RouterService(engine)

        low_decision = await service.route(task=low_risk.task)
        high_decision = await service.route(task=high_risk.task)

        assert low_decision.workload_class == "bulk_implementation"
        assert high_decision.workload_class == "architectural_reasoning"
        assert low_decision.selected_worker_profile_id == PROFILE_LONGCONTEXT_ECONOMY
        assert high_decision.selected_worker_profile_id == PROFILE_PREMIUM_REASONING
        assert (
            low_decision.selected_worker_profile_id
            != high_decision.selected_worker_profile_id
        )
        assert low_decision.decision_hash != high_decision.decision_hash
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_no_eligible_worker_persists_a_real_escalation(
    tmp_path: Path,
) -> None:
    """Chapter 6.1 gate 9: a task whose hard policy gate (`requires_approval`
    and `approval_satisfied=False`) denies every candidate still produces a
    real, persisted `RouteDecision` naming the escalation target — not an
    exception, not a partially-written row. Passing `approval_satisfied=True`
    is the DDE-026 production path when an Approval row already exists."""
    engine = new_engine()
    try:
        fixture = await build_routing_fixture(
            engine,
            tmp_path,
            mission_slug="MISSION-ROUTE-NOROUTE",
            task_class="implementation",
            requires_approval=True,
        )
        service = RouterService(engine)

        decision = await service.route(task=fixture.task)

        assert decision.selected_worker_profile_id == HUMAN_DECISION_TASK
        assert "HARD_GATE_APPROVAL_REQUIRED" in decision.reason_codes
        assert "NO_ELIGIBLE_WORKER" in decision.reason_codes
        assert decision.fallback_plan == []
        assert all(
            candidate["eliminated_at_gate"] == 0 for candidate in decision.candidates
        )

        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            reloaded = await RouteDecisionRepository().get_route_decision(
                uow.connection, decision.decision_id
            )
            await uow.commit()
        assert reloaded == decision
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_service_read_methods_and_shared_unit_of_work(tmp_path: Path) -> None:
    """`RouterService.get_route_decision`/`list_for_task` (the same
    read-method pattern as `TaskGraphService.get_task_graph`), and a
    caller-supplied `uow` (Chapter 3.5: a transaction may span module
    boundaries) commits alongside the caller's own write instead of
    opening an independent transaction."""
    engine = new_engine()
    try:
        fixture = await build_routing_fixture(
            engine, tmp_path, mission_slug="MISSION-ROUTE-SHARED-UOW"
        )
        service = RouterService(engine)

        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            decision = await service.route(task=fixture.task, uow=uow)
            await uow.commit()

        by_id = await service.get_route_decision(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            decision_id=decision.decision_id,
        )
        assert by_id == decision

        for_task = await service.list_for_task(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            task_id=fixture.task.task_id,
        )
        assert for_task == [decision]

        missing = await service.get_route_decision(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            decision_id=fixture.task.task_id,
        )
        assert missing is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_recompute_produces_a_new_independent_row_with_stable_hash(
    tmp_path: Path,
) -> None:
    """Chapter 3.10: RouteDecision definitions are immutable and RouteDecision
    carries no `version` column (unlike ContextPackage/TaskGraph) — routing
    the same task twice against an unchanged policy inserts two independent
    rows sharing one `decision_hash`."""
    engine = new_engine()
    try:
        fixture = await build_routing_fixture(
            engine, tmp_path, mission_slug="MISSION-ROUTE-REPEAT"
        )
        service = RouterService(engine)

        first = await service.route(task=fixture.task)
        second = await service.route(task=fixture.task)

        assert first.decision_id != second.decision_id
        assert first.decision_hash == second.decision_hash

        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            for_task = await RouteDecisionRepository().list_for_task(
                uow.connection, fixture.task.task_id
            )
            await uow.commit()
        assert {row.decision_id for row in for_task} == {
            first.decision_id,
            second.decision_id,
        }
    finally:
        await engine.dispose()
