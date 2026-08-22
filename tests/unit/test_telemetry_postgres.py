"""PostgreSQL-backed Chapter 6.5 real-telemetry engine (Chapter 19.1).
Exercises the real production mutation call site --
`engine.verification.runner.VerificationRunnerService.run()`'s `PASSED`
and `FAILED` branches calling `engine.telemetry.service.
RoutingTelemetryService.record_decision_outcome()` inside the same
transaction as the terminal `VerificationRun` write -- against a real
database, not a fixture double.
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

from engine.attribution.repository import FailureAttributionRepository
from engine.context.repo import repo_root
from engine.telemetry.model import ACTUAL_COST_GAP_DISCLOSED
from engine.telemetry.repository import RoutingDecisionOutcomeRepository
from engine.truth.db import open_unit_of_work
from engine.verification.checks import CheckSpec
from engine.verification.oracle import AcceptanceOracleService
from engine.verification.runner import VerificationRunnerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.verification_fixtures import build_verification_fixture

CLEAN_MODULE = '''"""Scratch module for DDE-035 telemetry proof tests."""

from __future__ import annotations


def add(a: int, b: int) -> int:
    return a + b
'''

LINT_BROKEN_MODULE = """import os


def unused_import() -> None:
    return None
"""


@pytest.mark.asyncio
async def test_passed_verification_run_persists_real_telemetry(
    tmp_path: Path,
) -> None:
    """A genuinely PASSED `VerificationRun` leaves behind exactly one
    durable `RoutingDecisionOutcome` row, linked to the real
    `RouteDecision` behind the worker's `ExecutionPlan` -- never a
    detached, best-effort side write."""
    root = repo_root()
    db_engine = new_engine()
    workspace = None
    try:
        fixture = await build_verification_fixture(
            db_engine, tmp_path, mission_slug="MISSION-TELEMETRY-PASS"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(db_engine, root=root)
        workspaces.write(workspace, "verification_check.py", CLEAN_MODULE.encode())

        lint_outcome = CheckSpec(
            outcome_id=uuid4(),
            statement="ruff check reports no lint violations on verification_check.py",
            kind="test",
            ref="ruff:verification_check.py",
            command=[sys.executable, "-m", "ruff", "check", "verification_check.py"],
        )
        oracles = AcceptanceOracleService(db_engine)
        oracle = await oracles.define(
            task=fixture.task, outcomes=[lint_outcome], minimum_confidence=1.0
        )

        runner = VerificationRunnerService(db_engine, workspaces)
        run = await runner.run(
            task=fixture.task,
            worker_run=fixture.worker_run,
            workspace=fixture.workspace,
            oracle=oracle,
            idempotency_key="telemetry-run-pass-1",
        )
        assert run.status == "PASSED"

        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            telemetry = (
                await RoutingDecisionOutcomeRepository().get_by_verification_run(
                    uow.connection, run.verification_run_id
                )
            )
            await uow.commit()

        assert telemetry is not None
        assert telemetry.verification_run_id == run.verification_run_id
        assert telemetry.route_decision_id == fixture.execution_plan.route_decision_id
        assert telemetry.task_attempt_id == fixture.worker_run.task_attempt_id
        assert telemetry.actual_verified_outcome == "PASSED"
        assert telemetry.verification_confidence == 1.0
        assert telemetry.rework_count == 0
        assert telemetry.escalated is False
        assert telemetry.human_intervention_required is False
        assert telemetry.recovery_action is None
        assert telemetry.failure_class is None
        assert telemetry.elapsed_seconds is not None
        assert telemetry.elapsed_seconds >= 0.0
        assert telemetry.context_package_id == fixture.worker_run.context_package_id
        assert telemetry.capability_set == list(
            fixture.execution_plan.capability_requirements
        )
        assert telemetry.failure_attribution_id is None
        assert ACTUAL_COST_GAP_DISCLOSED in telemetry.disclosed_gaps
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(workspace=workspace)
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_failed_verification_run_links_the_real_failure_attribution(
    tmp_path: Path,
) -> None:
    """Chapter 6.5 names 'the attribution from Sec5.11' as one telemetry
    field -- this proves the real, same-transaction `FailureAttribution`
    row DDE-034 wrote is the exact one this row links to, not a
    placeholder or a later best-effort join."""
    root = repo_root()
    db_engine = new_engine()
    workspace = None
    try:
        fixture = await build_verification_fixture(
            db_engine, tmp_path, mission_slug="MISSION-TELEMETRY-FAIL"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(db_engine, root=root)
        workspaces.write(
            workspace, "verification_check.py", LINT_BROKEN_MODULE.encode()
        )

        lint_outcome = CheckSpec(
            outcome_id=uuid4(),
            statement="ruff check reports no lint violations on verification_check.py",
            kind="test",
            ref="ruff:verification_check.py",
            command=[sys.executable, "-m", "ruff", "check", "verification_check.py"],
        )
        oracles = AcceptanceOracleService(db_engine)
        oracle = await oracles.define(
            task=fixture.task, outcomes=[lint_outcome], minimum_confidence=1.0
        )

        runner = VerificationRunnerService(db_engine, workspaces)
        run = await runner.run(
            task=fixture.task,
            worker_run=fixture.worker_run,
            workspace=fixture.workspace,
            oracle=oracle,
            idempotency_key="telemetry-run-fail-1",
        )
        assert run.status == "FAILED"

        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            telemetry = (
                await RoutingDecisionOutcomeRepository().get_by_verification_run(
                    uow.connection, run.verification_run_id
                )
            )
            attribution = await FailureAttributionRepository().get_by_verification_run(
                uow.connection, run.verification_run_id
            )
            await uow.commit()

        assert telemetry is not None
        assert attribution is not None
        assert telemetry.actual_verified_outcome == "FAILED"
        assert telemetry.recovery_action == "repair"
        assert telemetry.failure_class == "VERIFICATION_FAILURE"
        assert telemetry.rework_count == 1
        assert telemetry.failure_attribution_id == attribution.attribution_id
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(workspace=workspace)
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_telemetry_is_idempotent_on_verification_run(tmp_path: Path) -> None:
    """AGENTS.md idempotency rule, enforced atomically (Chapter 6.5): a
    second real terminal write for the same `VerificationRun` id would
    hit the real `UNIQUE (verification_run_id)` constraint. Verified here
    directly against the repository's atomic insert-or-get, the same
    pattern `engine.attribution` uses."""
    root = repo_root()
    db_engine = new_engine()
    workspace = None
    try:
        fixture = await build_verification_fixture(
            db_engine, tmp_path, mission_slug="MISSION-TELEMETRY-IDEMPOTENT"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(db_engine, root=root)
        workspaces.write(workspace, "verification_check.py", CLEAN_MODULE.encode())
        lint_outcome = CheckSpec(
            outcome_id=uuid4(),
            statement="ruff check reports no lint violations on verification_check.py",
            kind="test",
            ref="ruff:verification_check.py",
            command=[sys.executable, "-m", "ruff", "check", "verification_check.py"],
        )
        oracles = AcceptanceOracleService(db_engine)
        oracle = await oracles.define(
            task=fixture.task, outcomes=[lint_outcome], minimum_confidence=1.0
        )
        runner = VerificationRunnerService(db_engine, workspaces)
        run = await runner.run(
            task=fixture.task,
            worker_run=fixture.worker_run,
            workspace=fixture.workspace,
            oracle=oracle,
            idempotency_key="telemetry-run-idempotent-1",
        )
        assert run.status == "PASSED"

        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            first = await RoutingDecisionOutcomeRepository().get_by_verification_run(
                uow.connection, run.verification_run_id
            )
            assert first is not None
            second, was_new = await RoutingDecisionOutcomeRepository().insert_or_get(
                uow.connection, first
            )
            await uow.commit()
        assert was_new is False
        assert second.outcome_id == first.outcome_id
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(workspace=workspace)
        await db_engine.dispose()
