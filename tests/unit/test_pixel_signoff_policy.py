"""DDE-068: human pixel sign-off can waive only a failed judge."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from engine.contracts.verification_run import CheckResult, VerificationRun
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.studio.pixel_signoff import pixel_signoff_scope


def _check(kind: str, status: str, ref: str) -> CheckResult:
    exit_code = 0 if status == "PASSED" else 1
    if status == "ERRORED":
        exit_code = -1
    return CheckResult(
        check_ref=ref,
        kind=kind,
        command=["fixture"],
        exit_code=exit_code,
        stdout="",
        stderr="",
        duration_ms=1,
        timed_out=status == "ERRORED",
        status=status,
    )


def _run(*checks: CheckResult, status: str = "FAILED") -> VerificationRun:
    now = datetime.now(UTC)
    return VerificationRun(
        verification_run_id=uuid7(),
        tenant_id=uuid7(),
        project_id=uuid7(),
        mission_id=uuid7(),
        task_id=uuid7(),
        task_attempt_id=uuid7(),
        worker_run_id=uuid7(),
        workspace_id=uuid7(),
        oracle_id=uuid7(),
        sequence=1,
        status=status,
        confidence=1.0,
        check_results=list(checks),
        outcome_results=[],
        negative_case_results=[],
        evidence_refs=[uuid7()],
        started_at=now,
        ended_at=now,
        created_at=now,
        updated_at=now,
    )


def test_signoff_scope_accepts_only_failed_judge_after_hard_passes() -> None:
    run = _run(
        _check("visual_diff", "PASSED", "visual:hard"),
        _check("security_scan", "PASSED", "security:hard"),
        _check("judge", "FAILED", "judge:polish"),
    )
    scope = pixel_signoff_scope(
        run,
        render_set_hash="sha256:render-set",
        design_authority_version="design-v4",
    )
    assert scope.failed_judge_refs == ("judge:polish",)
    assert scope.verification_run_id == str(run.verification_run_id)
    assert scope.evidence_refs == tuple(str(item) for item in run.evidence_refs)


def test_signoff_scope_rejects_deterministic_failure() -> None:
    run = _run(
        _check("visual_diff", "FAILED", "visual:density"),
        _check("judge", "FAILED", "judge:polish"),
    )
    with pytest.raises(DdeError) as exc:
        pixel_signoff_scope(
            run,
            render_set_hash="sha256:render-set",
            design_authority_version="design-v4",
        )
    assert exc.value.error_code == "POLICY_DENIED"
    assert exc.value.details["blocking_check_refs"] == ["visual:density"]


def test_signoff_scope_rejects_errored_judge() -> None:
    run = _run(
        _check("visual_diff", "PASSED", "visual:hard"),
        _check("judge", "ERRORED", "judge:polish"),
    )
    with pytest.raises(DdeError) as exc:
        pixel_signoff_scope(
            run,
            render_set_hash="sha256:render-set",
            design_authority_version="design-v4",
        )
    assert exc.value.error_code == "POLICY_DENIED"
    assert exc.value.details["blocking_check_refs"] == ["judge:polish"]


def test_signoff_scope_rejects_passed_run() -> None:
    run = _run(
        _check("visual_diff", "PASSED", "visual:hard"),
        _check("judge", "PASSED", "judge:polish"),
        status="PASSED",
    )
    with pytest.raises(DdeError) as exc:
        pixel_signoff_scope(
            run,
            render_set_hash="sha256:render-set",
            design_authority_version="design-v4",
        )
    assert exc.value.error_code == "POLICY_DENIED"
