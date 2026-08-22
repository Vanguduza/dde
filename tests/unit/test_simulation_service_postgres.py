"""PostgreSQL-backed Chapter 6.4 Routing Simulation Model (DDE-036).

Exercises the real production mutation call site --
`engine.simulation.service.RoutingSimulationService.run_regression()` --
against a real database, not a fixture double.
"""

from __future__ import annotations

import pytest

from engine.core.errors import DdeError
from engine.routing.policy import HUMAN_DECISION_TASK, POLICY_VERSION
from engine.simulation.scenarios import (
    SCENARIO_GENERATOR_INDEPENDENCE_VIOLATION,
    SCENARIO_HARD_GATE_APPROVAL_REQUIRED,
    SCENARIO_WORKER_OUTAGE,
)
from engine.simulation.service import MODEL_VERSION, RoutingSimulationService
from tests.support.db import new_engine, seed_tenant


@pytest.mark.asyncio
async def test_run_regression_persists_real_scenario_outcomes() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = RoutingSimulationService(engine)
        run = await service.run_regression(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            seed="rsm-real-1",
            scenario_classes=(
                SCENARIO_WORKER_OUTAGE,
                SCENARIO_GENERATOR_INDEPENDENCE_VIOLATION,
                SCENARIO_HARD_GATE_APPROVAL_REQUIRED,
            ),
            idempotency_key="rsm-run-real-1",
        )
        assert run.policy_version == POLICY_VERSION
        assert run.model_version == MODEL_VERSION
        assert run.experience_origin == "simulation"
        assert run.excluded_from_routing_learning is True
        assert run.disclosed_gaps == []
        assert len(run.scenario_results) == 3
        for result in run.scenario_results:
            assert result["selected_worker_profile_id"] == HUMAN_DECISION_TASK
            assert result["passed"] is True

        fetched = await service.get_run(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            run_id=run.run_id,
        )
        assert fetched is not None
        assert fetched.run_id == run.run_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_run_regression_discloses_deferred_scenario_classes() -> None:
    """A caller requesting a deferred class gets a real, disclosed gap on
    the persisted row -- never a silently-dropped request and never a
    fabricated result for that class."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = RoutingSimulationService(engine)
        run = await service.run_regression(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            seed="rsm-deferred-1",
            scenario_classes=(SCENARIO_WORKER_OUTAGE, "capability_gap"),
            idempotency_key="rsm-run-deferred-1",
        )
        assert len(run.scenario_results) == 1
        assert len(run.disclosed_gaps) == 1
        assert "capability_gap" in run.disclosed_gaps[0]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_run_regression_is_idempotent_on_idempotency_key() -> None:
    """AGENTS.md: a repeated command never launches a second mutation --
    the same `idempotency_key` returns the exact first `run_id`, not a
    newly generated one."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = RoutingSimulationService(engine)
        first = await service.run_regression(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            seed="rsm-idem-1",
            scenario_classes=(SCENARIO_WORKER_OUTAGE,),
            idempotency_key="rsm-run-idempotent-1",
        )
        second = await service.run_regression(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            seed="rsm-idem-1",
            scenario_classes=(SCENARIO_WORKER_OUTAGE,),
            idempotency_key="rsm-run-idempotent-1",
        )
        assert second.run_id == first.run_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_run_regression_rejects_unknown_scenario_class() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = RoutingSimulationService(engine)
        with pytest.raises(DdeError):
            await service.run_regression(
                tenant_id=tenant.tenant_id,
                project_id=tenant.project_id,
                seed="rsm-unknown-1",
                scenario_classes=("not_a_real_scenario",),
                idempotency_key="rsm-run-unknown-1",
            )
    finally:
        await engine.dispose()
