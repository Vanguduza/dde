"""Worker self-grading guardrails (research §4 item 1) -- pure policy and
the production runner's verdict-demotion path.

Production call site under test: `engine.verification.runner.
VerificationRunnerService.run` calls `assess_diff_independence` on the real
diff under verification BEFORE any oracle outcome executes
(`VerificationRunnerService._assess_guardrails`), records the findings on
every `Evidence.independence_flags` row it writes (`merge_flags`), and
demotes a would-be PASSED verdict to PARTIAL when a violation exists
(`runner._evaluate`). These tests exercise that policy purely -- no
PostgreSQL: `assess_diff_independence` is deliberately I/O-free so the
guardrail is unit-testable at all; the DB-backed wiring is covered by
tests/unit/test_verification_postgres.py's existing service-level suite.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from engine.contracts.acceptance_oracle import (
    AcceptanceOracle,
    EvidenceBinding,
    ObservableOutcome,
)
from engine.contracts.task import Task
from engine.contracts.verification_run import ObservableOutcomeResult
from engine.verification.guardrails import (
    INDEPENDENCE_FLAG_KEY,
    VIOLATION_FLAG_KEY,
    assess_diff_independence,
    merge_flags,
)
from engine.verification.repository import Evidence
from engine.verification.runner import _evaluate
from engine.verification.runner import merge_flags as runner_merge_flags


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
    from engine.verification.guardrails import TestScopeAssessment, TestScopeFinding

    violating = TestScopeAssessment(
        findings=(
            TestScopeFinding(
                kind="undeclared_test_edit",
                path="tests/test_payment.py",
                detail="diff touches a test-owned path",
                violation=True,
            ),
        )
    )
    clean = TestScopeAssessment(findings=())

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
