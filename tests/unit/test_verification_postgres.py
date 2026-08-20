"""PostgreSQL-backed `engine.verification`: schema, state-transition,
negative and recovery tests (Chapter 19.1) -- the mission's full acceptance
proof.

Every check below is a real, genuinely executed subprocess (`ruff check`,
`pytest`, a Python one-liner) run inside the real git worktree a completed
`WorkerRun` (Chapter 8.2, DDE-011) already occupies -- never a mock of this
module's own verification logic. Two of the scenarios below (PASS and FAIL)
prove the `AcceptanceOracle` renders two genuinely different, persisted
verdicts from two genuinely different real check outcomes.
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

from engine.context.repo import repo_root
from engine.contracts.task import Task
from engine.core.errors import DdeError
from engine.events.repository import EventsRepository
from engine.truth.db import open_unit_of_work
from engine.verification.checks import CheckSpec
from engine.verification.oracle import AcceptanceOracleService, validate_definition
from engine.verification.repository import (
    AcceptanceOracleRepository,
    EvidenceRepository,
    VerificationRunRepository,
)
from engine.verification.runner import VerificationRunnerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.verification_fixtures import build_verification_fixture

CLEAN_MODULE = '''"""Scratch module for DDE-012 verification proof tests."""

from __future__ import annotations


def add(a: int, b: int) -> int:
    return a + b
'''

PASSING_TEST_MODULE = """from verification_check import add


def test_add() -> None:
    assert add(2, 3) == 5
"""

LINT_BROKEN_MODULE = """import os


def unused_import() -> None:
    return None
"""


def _no_breakpoint_command() -> list[str]:
    return [
        sys.executable,
        "-c",
        "import pathlib, sys; "
        "sys.exit(0 if 'pdb.set_trace()' in "
        "pathlib.Path('verification_check.py').read_text() else 1)",
    ]


@pytest.mark.asyncio
async def test_schema_state_transition_pass_verdict_and_recovery(
    tmp_path: Path,
) -> None:
    """Real `ruff check` + real `pytest` + a real negative-case check all
    genuinely pass -> a real, persisted `PASSED` verdict with full evidence,
    reproduced exactly by a fresh session (Chapter 19.1 recovery)."""
    root = repo_root()
    db_engine = new_engine()
    workspace = None
    try:
        fixture = await build_verification_fixture(
            db_engine, tmp_path, mission_slug="MISSION-VERIFICATION-PASS"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(db_engine, root=root)
        workspaces.write(workspace, "verification_check.py", CLEAN_MODULE.encode())
        workspaces.write(
            workspace, "test_verification_check.py", PASSING_TEST_MODULE.encode()
        )

        lint_outcome = CheckSpec(
            outcome_id=uuid4(),
            statement="ruff check reports no lint violations on verification_check.py",
            kind="test",
            ref="ruff:verification_check.py",
            command=[sys.executable, "-m", "ruff", "check", "verification_check.py"],
        )
        unit_outcome = CheckSpec(
            outcome_id=uuid4(),
            statement="pytest passes for test_verification_check.py",
            kind="test",
            ref="pytest:test_verification_check.py",
            command=[
                sys.executable,
                "-m",
                "pytest",
                "test_verification_check.py",
                "-q",
            ],
        )
        no_breakpoint = CheckSpec(
            outcome_id=uuid4(),
            statement="no pdb breakpoint left in verification_check.py",
            kind="invariant",
            ref="invariant:no-breakpoint",
            command=_no_breakpoint_command(),
            is_negative_case=True,
        )

        oracles = AcceptanceOracleService(db_engine)
        oracle = await oracles.define(
            task=fixture.task,
            outcomes=[lint_outcome, unit_outcome, no_breakpoint],
            minimum_confidence=1.0,
        )
        assert oracle.scope == "task"
        assert oracle.task_id == fixture.task.task_id
        assert len(oracle.observable_outcomes) == 2
        assert len(oracle.negative_cases) == 1
        assert oracle.approved_by == "system:acceptance_oracle_v1"

        # Immutable/content-addressed (Chapter 3.10): re-defining the exact
        # same oracle from the same task returns the same row, not a copy.
        replayed_oracle = await oracles.define(
            task=fixture.task,
            outcomes=[lint_outcome, unit_outcome, no_breakpoint],
            minimum_confidence=1.0,
        )
        assert replayed_oracle.oracle_id == oracle.oracle_id

        runner = VerificationRunnerService(db_engine, workspaces)
        run = await runner.run(
            task=fixture.task,
            worker_run=fixture.worker_run,
            workspace=fixture.workspace,
            oracle=oracle,
            idempotency_key="verification-run-pass-1",
        )

        assert run.status == "PASSED"
        assert run.confidence == 1.0
        assert run.sequence == 1
        assert run.task_attempt_id == fixture.worker_run.task_attempt_id
        assert run.worker_run_id == fixture.worker_run.run_id
        assert run.workspace_id == fixture.workspace.workspace_id
        assert run.oracle_id == oracle.oracle_id
        assert len(run.check_results) == 3
        assert len(run.outcome_results) == 2
        assert len(run.negative_case_results) == 1
        assert all(item.status == "PASSED" for item in run.outcome_results)
        assert all(item.status == "PASSED" for item in run.negative_case_results)
        assert len(run.evidence_refs) == 3
        assert run.ended_at is not None

        lint_result = next(
            item
            for item in run.check_results
            if item.check_ref == "ruff:verification_check.py"
        )
        assert lint_result.exit_code == 0
        assert lint_result.status == "PASSED"
        unit_result = next(
            item
            for item in run.check_results
            if item.check_ref == "pytest:test_verification_check.py"
        )
        assert unit_result.exit_code == 0
        assert "1 passed" in unit_result.stdout

        # State-transition (Chapter 3.8: RUNNING -> a single terminal state).
        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            events = await EventsRepository().list_events_for_aggregate(
                uow.connection, "verification_run", run.verification_run_id
            )
            evidence_rows = await EvidenceRepository().list_for_run(
                uow.connection, run.verification_run_id
            )
            await uow.commit()
        assert [event.event_type for event in events] == [
            "VerificationRunStarted",
            "VerificationRunPassed",
        ]
        assert len(evidence_rows) == 3
        for row in evidence_rows:
            assert row.status == "RECORDED"
            assert row.produced_by == "capability:engine.verification.runner"
            assert row.independence_flags["independent"] is True
            assert (
                row.independence_flags["generator_worker_profile_id"]
                == fixture.worker_run.worker_profile_id
            )

        # Recovery (Chapter 19.1): a brand-new engine/session reads back the
        # exact committed VerificationRun and Evidence rows.
        recovery_engine = new_engine()
        try:
            async with open_unit_of_work(
                recovery_engine,
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
            ) as uow:
                reloaded_run = await VerificationRunRepository().get_run(
                    uow.connection, run.verification_run_id
                )
                reloaded_oracle = await AcceptanceOracleRepository().get_oracle(
                    uow.connection, oracle.oracle_id
                )
                reloaded_evidence = await EvidenceRepository().list_for_run(
                    uow.connection, run.verification_run_id
                )
                await uow.commit()
        finally:
            await recovery_engine.dispose()
        assert reloaded_run == run
        assert reloaded_oracle == oracle
        assert {row.evidence_id for row in reloaded_evidence} == set(run.evidence_refs)
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(workspace=workspace)
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_negative_real_check_failure_produces_failed_verdict(
    tmp_path: Path,
) -> None:
    """A deliberately broken lint rule -- a real, unused import -- makes
    `ruff check` genuinely fail; the oracle must render a real, persisted
    `FAILED` verdict, distinct from the PASSED verdict above."""
    root = repo_root()
    db_engine = new_engine()
    workspace = None
    try:
        fixture = await build_verification_fixture(
            db_engine, tmp_path, mission_slug="MISSION-VERIFICATION-FAIL"
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
            idempotency_key="verification-run-fail-1",
        )

        assert run.status == "FAILED"
        assert run.confidence == 0.0
        assert len(run.check_results) == 1
        failed_check = run.check_results[0]
        assert failed_check.status == "FAILED"
        assert failed_check.exit_code != 0
        combined_output = failed_check.stdout + failed_check.stderr
        assert "F401" in combined_output

        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            events = await EventsRepository().list_events_for_aggregate(
                uow.connection, "verification_run", run.verification_run_id
            )
            await uow.commit()
        assert [event.event_type for event in events] == [
            "VerificationRunStarted",
            "VerificationRunFailed",
        ]
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(workspace=workspace)
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_negative_erroring_check_command_is_captured_not_raised(
    tmp_path: Path,
) -> None:
    """Chapter 19.1's negative fixture: a check command that itself cannot
    even run (nonexistent executable) is captured as a real, typed
    `ERRORED` result -- never an unhandled exception."""
    root = repo_root()
    db_engine = new_engine()
    workspace = None
    try:
        fixture = await build_verification_fixture(
            db_engine, tmp_path, mission_slug="MISSION-VERIFICATION-ERROR"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(db_engine, root=root)

        broken_binding = CheckSpec(
            outcome_id=uuid4(),
            statement="a command that cannot even be spawned",
            kind="test",
            ref="invariant:unspawnable",
            command=["dde-definitely-not-a-real-executable-xyz"],
        )
        oracles = AcceptanceOracleService(db_engine)
        oracle = await oracles.define(
            task=fixture.task, outcomes=[broken_binding], minimum_confidence=1.0
        )

        runner = VerificationRunnerService(db_engine, workspaces)
        run = await runner.run(
            task=fixture.task,
            worker_run=fixture.worker_run,
            workspace=fixture.workspace,
            oracle=oracle,
            idempotency_key="verification-run-errored-1",
        )

        assert run.status == "ERRORED"
        assert run.confidence == 0.0
        assert len(run.check_results) == 1
        errored_check = run.check_results[0]
        assert errored_check.status == "ERRORED"
        assert errored_check.exit_code == -1
        assert errored_check.stderr
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(workspace=workspace)
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_idempotent_verification_run_replays(tmp_path: Path) -> None:
    """AGENTS.md's idempotency-key rule: a repeated `run()` call with the
    same key never re-executes the checks or writes a second row."""
    root = repo_root()
    db_engine = new_engine()
    workspace = None
    try:
        fixture = await build_verification_fixture(
            db_engine, tmp_path, mission_slug="MISSION-VERIFICATION-IDEMPOTENT"
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

        first = await runner.run(
            task=fixture.task,
            worker_run=fixture.worker_run,
            workspace=fixture.workspace,
            oracle=oracle,
            idempotency_key="verification-run-idempotent-1",
        )
        second = await runner.run(
            task=fixture.task,
            worker_run=fixture.worker_run,
            workspace=fixture.workspace,
            oracle=oracle,
            idempotency_key="verification-run-idempotent-1",
        )
        assert second.verification_run_id == first.verification_run_id

        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            runs_for_worker_run = await VerificationRunRepository().list_for_worker_run(
                uow.connection, fixture.worker_run.run_id
            )
            evidence_rows = await EvidenceRepository().list_for_run(
                uow.connection, first.verification_run_id
            )
            await uow.commit()
        assert len(runs_for_worker_run) == 1
        assert len(evidence_rows) == 1
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(workspace=workspace)
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_negative_worker_run_not_completed_is_rejected(tmp_path: Path) -> None:
    """Chapter 3.9 step 14: verification consumes durable outputs -- it
    never races a `WorkerRun` that has not reached `COMPLETED`."""
    root = repo_root()
    db_engine = new_engine()
    workspace = None
    try:
        fixture = await build_verification_fixture(
            db_engine, tmp_path, mission_slug="MISSION-VERIFICATION-NOT-DONE"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(db_engine, root=root)
        not_completed = fixture.worker_run.model_copy(
            update={"status": "PLANNED", "ended_at": None}
        )

        lint_outcome = CheckSpec(
            outcome_id=uuid4(),
            statement="unused",
            kind="test",
            ref="unused",
            command=[sys.executable, "-c", "print('unused')"],
        )
        oracles = AcceptanceOracleService(db_engine)
        oracle = await oracles.define(
            task=fixture.task, outcomes=[lint_outcome], minimum_confidence=1.0
        )
        runner = VerificationRunnerService(db_engine, workspaces)

        with pytest.raises(DdeError) as excinfo:
            await runner.run(
                task=fixture.task,
                worker_run=not_completed,
                workspace=fixture.workspace,
                oracle=oracle,
                idempotency_key="verification-run-not-done-1",
            )
        assert excinfo.value.error_code == "POLICY_DENIED"

        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            runs_for_worker_run = await VerificationRunRepository().list_for_worker_run(
                uow.connection, fixture.worker_run.run_id
            )
            await uow.commit()
        assert runs_for_worker_run == []
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(workspace=workspace)
        await db_engine.dispose()


def test_negative_oracle_definition_validation_rejects_unexecutable_bindings() -> None:
    """Chapter 4.4 (1-5 observable criteria) and this Stage 1 runner's
    executability constraints (no `judge`/`human`, no missing command) are
    enforced before any oracle is ever persisted."""
    outcome_id = uuid4()

    with pytest.raises(DdeError) as too_few:
        validate_definition(
            scope="task",
            observable_outcomes=[],
            negative_cases=[],
            minimum_confidence=1.0,
        )
    assert too_few.value.error_code == "ORACLE_UNSATISFIED"

    with pytest.raises(DdeError) as mission_scope:
        validate_definition(
            scope="mission",
            observable_outcomes=[
                CheckSpec(
                    outcome_id=outcome_id,
                    statement="s",
                    kind="test",
                    ref="r",
                    command=["true"],
                )
            ],
            negative_cases=[],
            minimum_confidence=1.0,
        )
    assert mission_scope.value.error_code == "ORACLE_UNSATISFIED"

    with pytest.raises(DdeError) as judge_kind:
        validate_definition(
            scope="task",
            observable_outcomes=[
                CheckSpec(
                    outcome_id=outcome_id,
                    statement="a certified model judges this",
                    kind="judge",
                    ref="judge-ref",
                    command=[],
                )
            ],
            negative_cases=[],
            minimum_confidence=1.0,
        )
    assert judge_kind.value.error_code == "ORACLE_UNSATISFIED"

    with pytest.raises(DdeError) as missing_command:
        validate_definition(
            scope="task",
            observable_outcomes=[
                CheckSpec(
                    outcome_id=outcome_id,
                    statement="s",
                    kind="test",
                    ref="r",
                    command=[],
                )
            ],
            negative_cases=[],
            minimum_confidence=1.0,
        )
    assert missing_command.value.error_code == "ORACLE_UNSATISFIED"

    with pytest.raises(DdeError) as bad_confidence:
        validate_definition(
            scope="task",
            observable_outcomes=[
                CheckSpec(
                    outcome_id=outcome_id,
                    statement="s",
                    kind="test",
                    ref="r",
                    command=["true"],
                )
            ],
            negative_cases=[],
            minimum_confidence=1.5,
        )
    assert bad_confidence.value.error_code == "ORACLE_UNSATISFIED"


@pytest.mark.asyncio
async def test_negative_high_risk_oracle_requires_explicit_approval(
    tmp_path: Path,
) -> None:
    """Chapter 11.2's oracle-first rule: a `risk_class >= high` task cannot
    auto-approve its own oracle."""
    root = repo_root()
    db_engine = new_engine()
    workspace = None
    try:
        fixture = await build_verification_fixture(
            db_engine, tmp_path, mission_slug="MISSION-VERIFICATION-HIGH-RISK"
        )
        workspace = fixture.workspace
        high_risk_task: Task = fixture.task.model_copy(update={"risk_class": "high"})
        lint_outcome = CheckSpec(
            outcome_id=uuid4(),
            statement="unused",
            kind="test",
            ref="unused",
            command=[sys.executable, "-c", "print('unused')"],
        )
        oracles = AcceptanceOracleService(db_engine)

        with pytest.raises(DdeError) as excinfo:
            await oracles.define(
                task=high_risk_task, outcomes=[lint_outcome], minimum_confidence=1.0
            )
        assert excinfo.value.error_code == "POLICY_DENIED"

        approved = await oracles.define(
            task=high_risk_task,
            outcomes=[lint_outcome],
            minimum_confidence=1.0,
            approved_by="governance:reviewer-1",
        )
        assert approved.approved_by == "governance:reviewer-1"
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(workspace=workspace)
        await db_engine.dispose()
