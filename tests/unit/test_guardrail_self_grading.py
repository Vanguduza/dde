"""Worker self-grading guardrails (research §4 item 1) -- pure policy, the
production runner's verdict-demotion path, and the SCOPE_VIOLATION
classification bridge into Chapter 12.3's recovery machinery.

Production call site under test: `engine.verification.runner.
VerificationRunnerService.run` calls `assess_diff_independence` on the real
diff under verification BEFORE any oracle outcome executes
(`VerificationRunnerService._assess_guardrails`), records the findings on
every `Evidence.independence_flags` row it writes (`merge_flags`), demotes
a would-be PASSED verdict to PARTIAL when a violation exists
(`runner._evaluate`), and durably FAILS the run's `TaskAttempt` with
`failure_class="SCOPE_VIOLATION"` (`_fail_unverified_attempt`) -- the exact
surface `RecoveryService.assert_clear_to_retry`
(`engine.recovery.dispatch`) already reads through
`engine.recovery.matrix.decide`, landing on the reject / requires_human /
allow_new_worker_run=False row (never a silent retry).

The pure-policy tests run without PostgreSQL; the DB-backed test follows
the tests/unit/test_telemetry_postgres.py fixture chain
(`build_verification_fixture`) against a real database.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from sys import executable
from uuid import uuid4

import pytest

from engine.context.repo import repo_root
from engine.contracts.acceptance_oracle import (
    AcceptanceOracle,
    EvidenceBinding,
    ObservableOutcome,
)
from engine.contracts.task import Task
from engine.contracts.verification_run import ObservableOutcomeResult
from engine.missions.attempts import TaskAttemptService
from engine.recovery.matrix import decide
from engine.telemetry.repository import RoutingDecisionOutcomeRepository
from engine.truth.db import open_unit_of_work
from engine.verification.checks import CheckSpec
from engine.verification.guardrails import (
    INDEPENDENCE_FLAG_KEY,
    VIOLATION_FLAG_KEY,
    assess_diff_independence,
    merge_flags,
)
from engine.verification.guardrails import (
    TestScopeAssessment as GuardrailAssessment,
)
from engine.verification.guardrails import (
    TestScopeFinding as GuardrailFinding,
)
from engine.verification.oracle import AcceptanceOracleService
from engine.verification.repository import Evidence, EvidenceRepository
from engine.verification.runner import VerificationRunnerService, _evaluate
from engine.verification.runner import merge_flags as runner_merge_flags
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.verification_fixtures import build_verification_fixture


def _task(*, write_scope: list[str] | None = None) -> Task:
    now = datetime.now(UTC)
    return Task(
        task_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        mission_id=uuid4(),
        graph_id=uuid4(),
        title="add feature",
        intent="implement a function",
        task_class="implementation",
        requirement_refs=[],
        feature_refs=[],
        success_criteria=[],
        expected_write_scope=write_scope or [],
        expected_read_scope=[],
        blast_radius="local",
        risk_class="medium",
        estimated_effort="m",
        autonomy_ceiling=1,
        requires_approval=False,
        status="EXECUTING",
        lock_version=1,
        created_at=now,
        updated_at=now,
    )


def _oracle(*, binding_refs: list[str]) -> AcceptanceOracle:
    now = datetime.now(UTC)
    outcomes = [
        ObservableOutcome(
            outcome_id=uuid4(),
            statement="suite passes",
            evidence_binding=EvidenceBinding(kind="test", ref=ref, command=["pytest"]),
        )
        for ref in binding_refs
    ]
    return AcceptanceOracle(
        oracle_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        mission_id=uuid4(),
        task_id=None,
        oracle_version="v1",
        scope="mission",
        requirement_refs=[],
        feature_refs=[],
        observable_outcomes=outcomes,
        domain_invariants=[],
        negative_cases=[],
        minimum_confidence=1.0,
        human_assertions=[],
        created_at=now,
        updated_at=now,
    )


def _outcome_result(status: str) -> list[ObservableOutcomeResult]:
    return [
        ObservableOutcomeResult(
            outcome_id=uuid4(),
            statement="suite passes",
            is_negative_case=False,
            check_ref="tests/test_x.py",
            status=status,
            evaluated_at=datetime.now(UTC),
        )
    ]


def test_undeclared_edit_to_test_file_is_a_violation() -> None:
    """SWE-bench #538's core attack: the worker edits its own tests. The
    diff touches `tests/test_payment.py`, the task's declared write scope
    covers only product code -- must be flagged as a harness-gaming
    violation at the runner's pre-oracle call site."""
    assessment = assess_diff_independence(
        task=_task(write_scope=["src/payments/"]),
        oracle=_oracle(binding_refs=[]),
        changed_files=[
            "src/payments/service.py",
            "tests/test_payment.py",
        ],
    )
    violations = assessment.violations
    assert len(violations) == 1
    assert violations[0].kind == "undeclared_test_edit"
    assert violations[0].path == "tests/test_payment.py"


def test_task_authorized_test_edit_is_not_flagged() -> None:
    """A task whose declared write scope explicitly includes the test tree
    (e.g. a repair task chartered to fix a broken test) is legitimate --
    no violation may be recorded for exactly-authorized paths."""
    assessment = assess_diff_independence(
        task=_task(write_scope=["src/payments/", "tests/test_payment.py"]),
        oracle=_oracle(binding_refs=[]),
        changed_files=["tests/test_payment.py"],
    )
    assert assessment.violations == ()
    assert assessment.findings == ()


def test_added_file_shadowing_oracle_declared_layout_is_a_violation() -> None:
    """The second documented attack: a patch adds a file where the oracle
    expects to FIND its own test, displacing/shadowing the real suite. The
    added path sits inside the same directory as an oracle-declared test
    binding ref."""
    assessment = assess_diff_independence(
        task=_task(write_scope=["src/"]),
        oracle=_oracle(
            binding_refs=["tests/e2e/test_checkout_flow.py"],
        ),
        changed_files=["src/checkout.py", "tests/e2e/conftest.py"],
    )
    kinds = {item.kind for item in assessment.violations}
    assert "added_file_shadows_expected_test_layout" in kinds
    shadow = next(
        item
        for item in assessment.violations
        if item.kind == "added_file_shadows_expected_test_layout"
    )
    assert "test_checkout_flow.py" in shadow.detail


def test_product_only_diff_produces_no_findings() -> None:
    """The honest default: a diff touching only declared product code
    yields zero findings and both flag keys explicitly False/empty."""
    assessment = assess_diff_independence(
        task=_task(write_scope=["src/checkout/"]),
        oracle=_oracle(binding_refs=["tests/test_checkout.py"]),
        changed_files=["src/checkout/service.py"],
    )
    assert assessment.findings == ()
    flags = assessment.as_flags()
    assert flags[INDEPENDENCE_FLAG_KEY] == []
    assert flags[VIOLATION_FLAG_KEY] is False


def test_windows_style_paths_are_normalised() -> None:
    """Workspace git on Windows reports backslash-separated paths; the
    policy must not let a separator dodge the sweep."""
    assessment = assess_diff_independence(
        task=_task(write_scope=["src/"]),
        oracle=_oracle(binding_refs=[]),
        changed_files=["tests\\test_payment.py"],
    )
    assert len(assessment.violations) == 1
    assert assessment.violations[0].path == "tests/test_payment.py"


def test_clean_pass_over_violating_diff_is_demoted_to_partial() -> None:
    """The runner's verdict rule (`runner._evaluate`): every check passed
    and confidence cleared the bar, but the guardrail recorded a violation
    -- the run must NOT certify PASSED; it lands as PARTIAL so downstream
    integration gates treat it as untrusted. The guardrail never improves
    a failing result."""
    results = _outcome_result("PASSED")

    violating = GuardrailAssessment(
        findings=(
            GuardrailFinding(
                kind="undeclared_test_edit",
                path="tests/test_payment.py",
                detail="diff touches a test-owned path",
                violation=True,
            ),
        )
    )
    clean = GuardrailAssessment(findings=())

    assert _evaluate(
        outcome_results=results,
        negative_results=[],
        minimum_confidence=1.0,
        guardrail=violating,
    ) == ("PARTIAL", 1.0)
    assert _evaluate(
        outcome_results=results,
        negative_results=[],
        minimum_confidence=1.0,
        guardrail=clean,
    ) == ("PASSED", 1.0)
    failing = _outcome_result("FAILED")
    assert (
        _evaluate(
            outcome_results=failing,
            negative_results=[],
            minimum_confidence=1.0,
            guardrail=violating,
        )[0]
        == "FAILED"
    )


def test_merge_flags_preserves_independence_record_and_adds_findings() -> None:
    """Evidence rows keep the generator/verifier separation record AND
    carry the guardrail findings -- one dict, neither key set clobbering
    the other (`runner.merge_flags` re-exports `guardrails.merge_flags`;
    this pins that contract)."""
    base = {
        "generator_worker_profile_id": "profile.deterministic_runner",
        "verifier": "engine.verification.runner",
        "independent": True,
    }
    assessment = assess_diff_independence(
        task=_task(write_scope=[]),
        oracle=_oracle(binding_refs=[]),
        changed_files=["tests/test_x.py"],
    )
    merged = merge_flags(base, assessment)
    assert merged["independent"] is True
    assert merged["generator_worker_profile_id"] == "profile.deterministic_runner"
    assert isinstance(merged[INDEPENDENCE_FLAG_KEY], list)
    assert merged[VIOLATION_FLAG_KEY] is True
    assert runner_merge_flags is merge_flags


def test_evidence_contract_accepts_guardrail_flags() -> None:
    """`independence_flags` is free-form (`additionalProperties: true`) in
    the generated contract -- prove a real `Evidence` row accepts the new
    keys so the persisted record cannot reject them."""
    now = datetime.now(UTC)
    evidence = Evidence(
        evidence_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        mission_id=uuid4(),
        task_id=uuid4(),
        verification_run_id=uuid4(),
        integrated_revision="abc123",
        evidence_type="test",
        artifact_refs=[],
        content_hash="h",
        signature="s",
        produced_by="capability:engine.verification.runner",
        independence_flags={
            "independent": True,
            INDEPENDENCE_FLAG_KEY: [{"kind": "undeclared_test_edit"}],
            VIOLATION_FLAG_KEY: True,
        },
        recorded_at=now,
        status="RECORDED",
        created_at=now,
        updated_at=now,
    )
    assert evidence.independence_flags[VIOLATION_FLAG_KEY] is True


def test_guardrail_violation_class_maps_to_never_silent_retry_row() -> None:
    """The classification wired onto the TaskAttempt must be one the
    existing recovery machinery treats as never-silent-retry:
    `engine.recovery.matrix.decide("SCOPE_VIOLATION")` is Chapter 12.3's
    reject / requires_human / no-new-WorkerRun row -- the same row
    `RecoveryService.assert_clear_to_retry` raises on before any retry."""
    decision = decide("SCOPE_VIOLATION", occurrence_count=1)
    assert decision.failure_class == "SCOPE_VIOLATION"
    assert decision.action == "reject"
    assert decision.requires_human is True
    assert decision.allow_new_worker_run is False
    assert decision.retryable is False


CLEAN_MODULE = '''"""Scratch module for the guardrail proof tests."""

from __future__ import annotations


def add(a: int, b: int) -> int:
    return a + b
'''

VIOLATING_TEST_MODULE = '''"""Harness-gaming payload for the guardrail proof test."""

from __future__ import annotations


def test_always_passes() -> None:
    assert True
'''


@pytest.mark.asyncio
async def test_violating_diff_run_is_partial_and_classified_scope_violation(
    tmp_path: Path,
) -> None:
    """End to end over the real fixture chain (the
    tests/unit/test_telemetry_postgres.py pattern): a diff that overwrites a
    tracked file under `tests/` -- outside the fixture task's declared
    write scope, inside a conventional test directory -- still passes every
    check, but the run lands PARTIAL (never PASSED), carries the guardrail
    violation on its evidence rows, gets NO telemetry outcome row (Chapter
    6.5's actual_verified_outcome enum admits only PASSED/FAILED), and
    leaves the durable SCOPE_VIOLATION classification exactly where the
    recovery path reads it: a FAILED `TaskAttempt.failure_class`.
    """
    root = repo_root()
    db_engine = new_engine()
    workspace = None
    try:
        fixture = await build_verification_fixture(
            db_engine, tmp_path, mission_slug="MISSION-GUARDRAIL-SCOPE"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(db_engine, root=root)
        workspaces.write(workspace, "verification_check.py", CLEAN_MODULE.encode())
        # The harness-gaming edit: overwriting a tracked, test-owned module
        # (tracked so it is visible to `git diff --name-only`, which skips
        # untracked files), outside the task's
        # expected_write_scope=["engine/routing"].
        workspaces.write(
            workspace,
            "tests/unit/test_telemetry_postgres.py",
            VIOLATING_TEST_MODULE.encode(),
        )

        lint_outcome = CheckSpec(
            outcome_id=uuid4(),
            statement="ruff check reports no lint violations on verification_check.py",
            kind="test",
            ref="ruff:verification_check.py",
            command=[executable, "-m", "ruff", "check", "verification_check.py"],
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
            idempotency_key="guardrail-run-violating-1",
        )
        assert run.status == "PARTIAL"

        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            evidence_rows = await EvidenceRepository().list_for_run(
                uow.connection, run.verification_run_id
            )
            telemetry = (
                await RoutingDecisionOutcomeRepository().get_by_verification_run(
                    uow.connection, run.verification_run_id
                )
            )
            attempt = await TaskAttemptService(db_engine).get_attempt(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                attempt_id=fixture.worker_run.task_attempt_id,
                uow=uow,
            )
            await uow.commit()

        assert evidence_rows
        for row in evidence_rows:
            flags = row.independence_flags
            assert flags[VIOLATION_FLAG_KEY] is True
            findings = flags[INDEPENDENCE_FLAG_KEY]
            assert isinstance(findings, list)
            assert any(item["violation"] for item in findings)

        assert telemetry is None

        assert attempt.status == "FAILED"
        assert attempt.failure_class == "SCOPE_VIOLATION"

        decision = decide(attempt.failure_class or "", occurrence_count=1)
        assert decision.action == "reject"
        assert decision.requires_human is True
        assert decision.allow_new_worker_run is False
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(workspace=workspace)
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_clean_diff_run_stays_passed_unclassified(tmp_path: Path) -> None:
    """The negative control: an identical pipeline without the violating
    edit stays PASSED, finalises its TaskAttempt COMPLETED (no failure
    class), and records its telemetry row unclassified -- the bridge never
    touches honest runs."""
    root = repo_root()
    db_engine = new_engine()
    workspace = None
    try:
        fixture = await build_verification_fixture(
            db_engine, tmp_path, mission_slug="MISSION-GUARDRAIL-CLEAN"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(db_engine, root=root)
        workspaces.write(workspace, "verification_check.py", CLEAN_MODULE.encode())

        lint_outcome = CheckSpec(
            outcome_id=uuid4(),
            statement="ruff check reports no lint violations on verification_check.py",
            kind="test",
            ref="ruff:verification_check.py",
            command=[executable, "-m", "ruff", "check", "verification_check.py"],
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
            idempotency_key="guardrail-run-clean-1",
        )
        assert run.status == "PASSED"

        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            evidence_rows = await EvidenceRepository().list_for_run(
                uow.connection, run.verification_run_id
            )
            telemetry = (
                await RoutingDecisionOutcomeRepository().get_by_verification_run(
                    uow.connection, run.verification_run_id
                )
            )
            attempt = await TaskAttemptService(db_engine).get_attempt(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                attempt_id=fixture.worker_run.task_attempt_id,
                uow=uow,
            )
            await uow.commit()

        assert evidence_rows
        for row in evidence_rows:
            assert row.independence_flags[VIOLATION_FLAG_KEY] is False

        assert telemetry is not None
        assert telemetry.actual_verified_outcome == "PASSED"
        assert telemetry.failure_class is None

        assert attempt.status == "COMPLETED"
        assert attempt.failure_class is None
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(workspace=workspace)
        await db_engine.dispose()
