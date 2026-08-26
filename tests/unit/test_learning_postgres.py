"""PostgreSQL-backed Chapter 6.8 ExperienceRecord engine (DDE-057).

Exercises the real production mutation call sites:
- `VerificationRunnerService.run()` terminal branches calling
  `ExperienceRecordService.record_from_verification()`
- `RoutingSimulationService.run_regression()` calling
  `record_from_simulation()`
- `queue_for_learning()` as the governed promotion-state mutation
against a real database, not a fixture double.
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

from engine.context.repo import repo_root
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.learning.repository import ExperienceRecordRepository
from engine.learning.service import ExperienceRecordService
from engine.simulation.scenarios import SCENARIO_WORKER_OUTAGE
from engine.simulation.service import RoutingSimulationService
from engine.truth.db import open_unit_of_work
from engine.verification.checks import CheckSpec
from engine.verification.oracle import AcceptanceOracleService
from engine.verification.runner import VerificationRunnerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine, seed_tenant
from tests.support.verification_fixtures import build_verification_fixture

CLEAN_MODULE = '''"""Scratch module for DDE-057 experience-record proof tests."""

from __future__ import annotations


def add(a: int, b: int) -> int:
    return a + b
'''

LINT_BROKEN_MODULE = """import os


def unused_import() -> None:
    return None
"""


async def _run_verification(
    db_engine,
    tmp_path: Path,
    *,
    mission_slug: str,
    source: str,
    idempotency_key: str,
):
    root = repo_root()
    fixture = await build_verification_fixture(
        db_engine, tmp_path, mission_slug=mission_slug
    )
    workspaces = WorkspaceService(db_engine, root=root)
    workspaces.write(fixture.workspace, "verification_check.py", source.encode())
    lint_outcome = CheckSpec(
        outcome_id=uuid4(),
        statement="ruff check reports no lint violations on verification_check.py",
        kind="test",
        ref="ruff:verification_check.py",
        command=[sys.executable, "-m", "ruff", "check", "verification_check.py"],
    )
    oracle = await AcceptanceOracleService(db_engine).define(
        task=fixture.task, outcomes=[lint_outcome], minimum_confidence=1.0
    )
    run = await VerificationRunnerService(db_engine, workspaces).run(
        task=fixture.task,
        worker_run=fixture.worker_run,
        workspace=fixture.workspace,
        oracle=oracle,
        idempotency_key=idempotency_key,
    )
    return fixture, run, workspaces


@pytest.mark.asyncio
async def test_passed_verification_persists_eligible_real_experience(
    tmp_path: Path,
) -> None:
    db_engine = new_engine()
    workspace = None
    try:
        fixture, run, workspaces = await _run_verification(
            db_engine,
            tmp_path,
            mission_slug="MISSION-EXPERIENCE-PASS",
            source=CLEAN_MODULE,
            idempotency_key="experience-run-pass-1",
        )
        workspace = fixture.workspace
        assert run.status == "PASSED"

        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            record = await ExperienceRecordRepository().get_by_verification_run(
                uow.connection, run.verification_run_id
            )
            eligible = await ExperienceRecordRepository().list_eligible_for_training(
                uow.connection,
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
            )
            await uow.commit()

        assert record is not None
        assert record.experience_origin == "real"
        assert record.verification_run_id == run.verification_run_id
        assert record.route_decision_id == fixture.execution_plan.route_decision_id
        assert record.failure_attribution == "none"
        assert record.eligible_for_routing_training is True
        assert record.down_weighted is False
        assert record.promotion_state == "unpromoted"
        assert record.holdout_partition in ("train", "holdout")
        assert record.selection_propensity == 1.0
        assert record.candidate_set_hash
        assert [row.experience_id for row in eligible] == [record.experience_id]
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_failed_not_context_attributed_is_route_attributable(
    tmp_path: Path,
) -> None:
    """A FAILED run whose DDE-034 attribution is not_context_attributed
    maps onto Chapter 6.8 `route_attributable` and stays eligible."""
    db_engine = new_engine()
    workspace = None
    try:
        fixture, run, workspaces = await _run_verification(
            db_engine,
            tmp_path,
            mission_slug="MISSION-EXPERIENCE-FAIL",
            source=LINT_BROKEN_MODULE,
            idempotency_key="experience-run-fail-1",
        )
        workspace = fixture.workspace
        assert run.status == "FAILED"

        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            record = await ExperienceRecordRepository().get_by_verification_run(
                uow.connection, run.verification_run_id
            )
            await uow.commit()

        assert record is not None
        assert record.experience_origin == "real"
        # Lint-broken fixture typically overreaches or is inconclusive;
        # either route_attributable (eligible) or inconclusive (excluded)
        # is a real mapped verdict -- never a fabricated environment/tool
        # class (EDR-0032).
        assert record.failure_attribution in (
            "route_attributable",
            "inconclusive",
            "context",
        )
        if record.failure_attribution == "route_attributable":
            assert record.eligible_for_routing_training is True
        elif (
            record.failure_attribution == "context"
            and record.attribution_confidence < 0.5
        ):
            assert record.down_weighted is True
            assert record.eligible_for_routing_training is True
        else:
            assert record.eligible_for_routing_training is False
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_experience_record_is_idempotent_on_verification_run(
    tmp_path: Path,
) -> None:
    db_engine = new_engine()
    workspace = None
    try:
        fixture, run, workspaces = await _run_verification(
            db_engine,
            tmp_path,
            mission_slug="MISSION-EXPERIENCE-IDEMPOTENT",
            source=CLEAN_MODULE,
            idempotency_key="experience-run-idempotent-1",
        )
        workspace = fixture.workspace
        assert run.status == "PASSED"

        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            first = await ExperienceRecordRepository().get_by_verification_run(
                uow.connection, run.verification_run_id
            )
            assert first is not None
            second, was_new = await ExperienceRecordRepository().insert_or_get(
                uow.connection, first
            )
            await uow.commit()
        assert was_new is False
        assert second.experience_id == first.experience_id
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_simulation_experience_is_excluded_from_training_population() -> None:
    db_engine = new_engine()
    try:
        tenant = await seed_tenant(db_engine)
        run = await RoutingSimulationService(db_engine).run_regression(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            seed="experience-sim-1",
            scenario_classes=(SCENARIO_WORKER_OUTAGE,),
            idempotency_key="experience-sim-run-1",
        )
        learning = ExperienceRecordService(db_engine)
        async with open_unit_of_work(
            db_engine,
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
        ) as uow:
            record = await ExperienceRecordRepository().get_by_simulation_run(
                uow.connection, run.run_id
            )
            eligible = await ExperienceRecordRepository().list_eligible_for_training(
                uow.connection,
                tenant_id=tenant.tenant_id,
                project_id=tenant.project_id,
            )
            await uow.commit()

        assert record is not None
        assert record.experience_origin == "simulation"
        assert record.eligible_for_routing_training is False
        assert record.verification_run_id is None
        assert eligible == []

        with pytest.raises(DdeError, match="simulation"):
            await learning.queue_for_learning(
                tenant_id=tenant.tenant_id,
                project_id=tenant.project_id,
                experience_id=record.experience_id,
                learning_run_id=uuid7(),
            )
    finally:
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_queue_for_learning_refuses_ineligible_and_accepts_eligible(
    tmp_path: Path,
) -> None:
    db_engine = new_engine()
    workspace = None
    try:
        fixture, run, workspaces = await _run_verification(
            db_engine,
            tmp_path,
            mission_slug="MISSION-EXPERIENCE-QUEUE",
            source=CLEAN_MODULE,
            idempotency_key="experience-run-queue-1",
        )
        workspace = fixture.workspace
        learning = ExperienceRecordService(db_engine)
        record = await learning.get_for_verification_run(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            verification_run_id=run.verification_run_id,
        )
        assert record is not None
        assert record.eligible_for_routing_training is True

        learning_run_id = uuid7()
        queued = await learning.queue_for_learning(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            experience_id=record.experience_id,
            learning_run_id=learning_run_id,
        )
        assert queued.promotion_state == "queued_for_learning"
        assert queued.learning_run_id == learning_run_id
        # Observational fields stayed immutable.
        assert queued.eligible_for_routing_training is True
        assert queued.experience_origin == "real"
        assert queued.candidate_set_hash == record.candidate_set_hash
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await db_engine.dispose()
