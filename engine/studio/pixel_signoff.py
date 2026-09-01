"""DDE-068 pixel-signoff eligibility over immutable verification evidence.

A human pixel sign-off is intentionally narrow: it may waive only a failed
subjective `judge` result after every deterministic/non-judge check has
already passed. It can never turn functional, accessibility, security,
density, silhouette, reduced-motion, timeout, or infrastructure failures
green.

This module is pure policy. Persistence and approval creation remain owned by
`FrontendStudioService` / `ApprovalService`.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.contracts.verification_run import VerificationRun
from engine.core.errors import DdeError


@dataclass(frozen=True)
class PixelSignoffScope:
    """Exact immutable evidence that a human is being asked to waive."""

    verification_run_id: str
    render_set_hash: str
    design_authority_version: str
    failed_judge_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    def as_payload(self) -> dict[str, object]:
        return {
            "verification_run_id": self.verification_run_id,
            "render_set_hash": self.render_set_hash,
            "design_authority_version": self.design_authority_version,
            "failed_judge_refs": list(self.failed_judge_refs),
            "evidence_refs": list(self.evidence_refs),
        }


def pixel_signoff_scope(
    run: VerificationRun,
    *,
    render_set_hash: str,
    design_authority_version: str,
) -> PixelSignoffScope:
    """Return a signable scope or fail closed with a typed policy refusal."""
    if not render_set_hash.strip():
        raise DdeError(
            "POLICY_DENIED",
            "pixel sign-off requires a non-empty render_set_hash",
            retryable=False,
        )
    if not design_authority_version.strip():
        raise DdeError(
            "POLICY_DENIED",
            "pixel sign-off requires a design_authority_version",
            retryable=False,
        )
    if run.status != "FAILED":
        raise DdeError(
            "POLICY_DENIED",
            "pixel sign-off is only legal for a failed verification run",
            retryable=False,
            details={
                "verification_run_id": str(run.verification_run_id),
                "status": run.status,
            },
        )

    judge_results = [result for result in run.check_results if result.kind == "judge"]
    hard_results = [result for result in run.check_results if result.kind != "judge"]
    if not judge_results:
        raise DdeError(
            "POLICY_DENIED",
            "pixel sign-off requires a judge result on the verification run",
            retryable=False,
            details={"verification_run_id": str(run.verification_run_id)},
        )

    hard_failures = [
        result.check_ref for result in hard_results if result.status != "PASSED"
    ]
    if hard_failures:
        raise DdeError(
            "POLICY_DENIED",
            "pixel sign-off cannot waive deterministic or non-judge failures",
            retryable=False,
            details={
                "verification_run_id": str(run.verification_run_id),
                "blocking_check_refs": hard_failures,
            },
        )

    invalid_judges = [
        result.check_ref
        for result in judge_results
        if result.status not in {"PASSED", "FAILED"}
    ]
    if invalid_judges:
        raise DdeError(
            "POLICY_DENIED",
            "pixel sign-off cannot waive an errored or incomplete judge",
            retryable=False,
            details={
                "verification_run_id": str(run.verification_run_id),
                "blocking_check_refs": invalid_judges,
            },
        )

    failed_judges = sorted(
        result.check_ref for result in judge_results if result.status == "FAILED"
    )
    if not failed_judges:
        raise DdeError(
            "POLICY_DENIED",
            "pixel sign-off is unnecessary because no judge check failed",
            retryable=False,
            details={"verification_run_id": str(run.verification_run_id)},
        )

    return PixelSignoffScope(
        verification_run_id=str(run.verification_run_id),
        render_set_hash=render_set_hash,
        design_authority_version=design_authority_version,
        failed_judge_refs=tuple(failed_judges),
        evidence_refs=tuple(str(ref) for ref in run.evidence_refs),
    )
