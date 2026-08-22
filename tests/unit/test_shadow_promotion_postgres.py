"""PostgreSQL-backed shadow-promotion flow (comparable-systems adoption
#8): real `routing_decision_outcomes` rows evaluated by the real
`RoutingSimulationService` mutation, persisted as a real
`routing_simulation_runs` row with `run_kind="shadow_promotion"`.

**Where the four outcome rows come from.** The production runner cannot
mint the controlled spread this scenario needs: a PASSED `VerificationRun`
always carries confidence 1.0 and a FAILED one 0.0 (`_evaluate` is
all-or-nothing), so over runner-produced PASSED/FAILED telemetry alone no
baseline/candidate floor pair ever yields the strict accept-rate
improvement promotion requires. The rows are therefore inserted through
the production `RoutingDecisionOutcomeRepository.insert_or_get` with the
outcome-side spread authored -- and every foreign key taken from real
objects: `route_decision_id` from the fixture `ExecutionPlan`,
`task_attempt_id` from the real `WorkerRun`, `context_package_id` from
that same run, and `verification_run_id` from real runner-produced
`VerificationRun` rows. Those runs are driven to PARTIAL deliberately:
every PASSED/FAILED terminal run claims its `verification_run_id` for the
Chapter 6.5 telemetry row written in the same transaction
(`UNIQUE (verification_run_id)`), while a PARTIAL run is terminal, fully
persisted, and carries no telemetry -- leaving its id free for the
authored row. No UUID without a backing row anywhere.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from engine.context.repo import repo_root
from engine.contracts.routing_decision_outcome import RoutingDecisionOutcome
from engine.contracts.verification_run import VerificationRun
from engine.core.errors import DdeError
from engine.simulation.repository import RoutingSimulationRunRepository
from engine.simulation.service import RoutingSimulationService
from engine.simulation.shadow_promotion import (
    SHADOW_PROMOTION_RUN_KIND,
    ShadowPromotionRequest,
)
from engine.telemetry.model import ACTUAL_COST_GAP_DISCLOSED
from engine.telemetry.repository import RoutingDecisionOutcomeRepository
from engine.truth.db import open_unit_of_work
from engine.verification.checks import CheckSpec
from engine.verification.oracle import AcceptanceOracleService
from engine.verification.runner import VerificationRunnerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine, seed_tenant
from tests.support.verification_fixtures import (
    VerificationFixture,
    build_verification_fixture,
)

_SCRATCH_MODULE = '''"""Scratch module for the shadow-promotion proof tests."""

from __future__ import annotations


def add(a: int, b: int) -> int:
    return a + b
'''


async def _produce_partial_verification_run(
    engine,
    fixture: VerificationFixture,
    *,
    idempotency_key: str,
) -> VerificationRun:
    """One real, terminal PARTIAL `VerificationRun` over the fixture's
    workspace: one genuinely passing probe and one genuinely failing probe
    give confidence 0.5 -- terminal and persisted, but (by Chapter 6.5's
    own rule) telemetry-free and attempt-neutral, so the same fixture can
    produce several of them and each leaves its `verification_run_id`
    unclaimed for the outcome row that will reference it."""
    root = repo_root()
    workspaces = WorkspaceService(engine, root=root)
    workspaces.write(
        workspace=fixture.workspace,
        relative_path="verification_check.py",
        content=_SCRATCH_MODULE.encode(),
    )
    passing_probe = CheckSpec(
        outcome_id=uuid4(),
        statement="the probe process exits 0",
        kind="test",
        ref="probe:passes",
        command=[sys.executable, "-c", "print('ok')"],
    )
    failing_probe = CheckSpec(
        outcome_id=uuid4(),
        statement="the probe process exits 0",
        kind="test",
        ref="probe:fails",
        command=[sys.executable, "-c", "raise SystemExit(3)"],
    )
    oracle = await AcceptanceOracleService(engine).define(
        task=fixture.task,
        outcomes=[passing_probe, failing_probe],
        minimum_confidence=1.0,
    )
    runner = VerificationRunnerService(engine, workspaces)
    run = await runner.run(
        task=fixture.task,
        worker_run=fixture.worker_run,
        workspace=fixture.workspace,
        oracle=oracle,
        idempotency_key=idempotency_key,
    )
    assert run.status == "PARTIAL", run
    return run


@pytest.mark.asyncio
async def test_shadow_promotion_records_measured_deltas_and_verdict(
    tmp_path: Path,
) -> None:
    """Seed four real outcome rows (3 pass, 1 gate-failed), evaluate a
    candidate that routes three of the four at a 0.9 floor, and prove the
    persisted run row carries `run_kind="shadow_promotion"`, the measured
    quadrant counts and deltas, and a promoted=True verdict -- without
    touching any live routing state.

    Policy direction under the honest semantics: `replay()` keeps the
    policy's decision (`routed = confidence >= floor`) apart from ground
    truth (`actual_verified_outcome`), and promotion keys on
    `success_yield` -- routed-and-passed over ALL decisions. The baseline
    here holds a 0.95 floor (it routes only the 1.0-confidence pass), the
    candidate widens to 0.9 (also routing the two mid-confidence passes,
    which really passed), so success_yield genuinely rises from 1/4 to
    3/4 while the doomed low-confidence failure stays unrouted by both.
    Promotion additionally requires wasted-accept non-regression, cost
    non-regression, and a quiet rollback trigger."""
    root = repo_root()
    db_engine = new_engine()
    workspace = None
    try:
        fixture = await build_verification_fixture(
            db_engine, tmp_path, mission_slug="MISSION-SHADOW-PROMO"
        )
        workspace = fixture.workspace
        runs = [
            await _produce_partial_verification_run(
                db_engine,
                fixture,
                idempotency_key=f"shadow-promo-partial-{index}",
            )
            for index in (1, 2, 3, 4)
        ]

        now = datetime.now(UTC)
        passed_rows = [
            (runs[0], 1.0, 10.0),
            (runs[1], 0.92, 12.0),
            (runs[2], 0.93, 11.0),
        ]
        failed_row = (runs[3], 0.2, 40.0)
        rows = [
            RoutingDecisionOutcome(
                outcome_id=uuid4(),
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                mission_id=fixture.mission.mission_id,
                task_id=fixture.task.task_id,
                route_decision_id=fixture.execution_plan.route_decision_id,
                task_attempt_id=fixture.worker_run.task_attempt_id,
                verification_run_id=run.verification_run_id,
                actual_verified_outcome="PASSED",
                verification_confidence=confidence,
                rework_count=0,
                escalated=False,
                human_intervention_required=False,
                recovery_action=None,
                failure_class=None,
                elapsed_seconds=elapsed,
                context_package_id=fixture.worker_run.context_package_id,
                capability_set=list(fixture.execution_plan.capability_requirements),
                failure_attribution_id=None,
                disclosed_gaps=[ACTUAL_COST_GAP_DISCLOSED],
                created_at=now,
                updated_at=now,
            )
            for run, confidence, elapsed in passed_rows
        ] + [
            RoutingDecisionOutcome(
                outcome_id=uuid4(),
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                mission_id=fixture.mission.mission_id,
                task_id=fixture.task.task_id,
                route_decision_id=fixture.execution_plan.route_decision_id,
                task_attempt_id=fixture.worker_run.task_attempt_id,
                verification_run_id=failed_row[0].verification_run_id,
                actual_verified_outcome="FAILED",
                verification_confidence=failed_row[1],
                rework_count=1,
                escalated=True,
                human_intervention_required=True,
                recovery_action="repair",
                failure_class="VERIFICATION_FAILURE",
                elapsed_seconds=failed_row[2],
                context_package_id=fixture.worker_run.context_package_id,
                capability_set=list(fixture.execution_plan.capability_requirements),
                failure_attribution_id=None,
                disclosed_gaps=[ACTUAL_COST_GAP_DISCLOSED],
                created_at=now,
                updated_at=now,
            )
        ]
        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            repository = RoutingDecisionOutcomeRepository()
            for row in rows:
                await repository.insert_or_get(uow.connection, row)
            await uow.commit()

        service = RoutingSimulationService(db_engine)
        request = ShadowPromotionRequest(
            baseline_policy={"accept_confidence_floor": 0.95},
            candidate_policy={"accept_confidence_floor": 0.9},
            max_cost_regression=1.0,
            rollback_trigger=lambda metrics: metrics.gate_fail_rate > 0.5,
        )
        run, decision = await service.evaluate_shadow_promotion(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            request=request,
            idempotency_key="shadow-promo-postgres-1",
        )

        assert run.scenario_classes == [SHADOW_PROMOTION_RUN_KIND]
        assert decision.promoted is True
        assert decision.baseline.decisions == 4
        assert decision.baseline.successes == 1
        assert decision.baseline.missed_passes == 2
        assert decision.candidate.successes == 3
        assert decision.candidate.wasted_accepts == 0
        assert decision.candidate.missed_passes == 0
        assert decision.candidate.correct_rejections == 1
        assert decision.baseline.success_yield == pytest.approx(1 / 4)
        assert decision.candidate.success_yield == pytest.approx(3 / 4)
        assert decision.success_yield_delta == pytest.approx(0.5)
        assert decision.wasted_accept_delta <= 0.0
        assert decision.cost_delta is not None
        assert decision.rollback_trigger_fired is False

        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            persisted = await RoutingSimulationRunRepository().get_run(
                uow.connection, run.run_id
            )
            await uow.commit()
        assert persisted is not None
        result = persisted.scenario_results[0]
        assert result["scenario_class"] == SHADOW_PROMOTION_RUN_KIND
        assert result["passed"] is True
        assert result["candidate_metrics"]["success_yield"] == pytest.approx(3 / 4)
        assert result["candidate_metrics"]["wasted_accepts"] == 0
        assert result["quadrants"]["candidate"]["successes"] == 3
        assert result["deltas"]["success_yield_delta"] == decision.success_yield_delta
        assert "actual_token_cost" in persisted.disclosed_gaps[0]

        # Idempotent replay returns the same durable row.
        replayed_run, replayed_decision = await service.evaluate_shadow_promotion(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            request=request,
            idempotency_key="shadow-promo-postgres-1",
        )
        assert replayed_run.run_id == run.run_id
        assert replayed_decision.promoted is True
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(workspace=workspace)
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_shadow_promotion_refuses_invalid_thresholds() -> None:
    db_engine = new_engine()
    try:
        tenant = await seed_tenant(db_engine)
        service = RoutingSimulationService(db_engine)
        with pytest.raises(DdeError):
            await service.evaluate_shadow_promotion(
                tenant_id=tenant.tenant_id,
                project_id=tenant.project_id,
                request=ShadowPromotionRequest(
                    candidate_policy={},
                    max_cost_regression=0.1,
                    rollback_trigger=lambda metrics: False,
                ),
                idempotency_key="shadow-promo-empty-1",
            )
        with pytest.raises(DdeError):
            await service.evaluate_shadow_promotion(
                tenant_id=tenant.tenant_id,
                project_id=tenant.project_id,
                request=ShadowPromotionRequest(
                    candidate_policy={"accept_confidence_floor": 0.5},
                    max_cost_regression=5.0,
                    rollback_trigger=lambda metrics: False,
                ),
                idempotency_key="shadow-promo-threshold-1",
            )
    finally:
        await db_engine.dispose()
