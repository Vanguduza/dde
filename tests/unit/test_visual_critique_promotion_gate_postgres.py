"""DDE-068: the multimodal visual verdict is machine-enforced at promotion.

Proves the last link of the chain the charter requires -- that a candidate
cannot become promotable on code validity alone. A rubric-blocked screen
produces a real FAILED `VerificationRun` and a real FAILED `TaskAttempt`
through the ordinary production path (`VerificationRunnerService.run()` ->
`_evaluate()` -> `_fail_unverified_attempt()` -> `TaskAttemptService.fail()`),
with no gate special-cased for this check kind.

The critic runtime is a deterministic stand-in so this proof is free and
repeatable; the live runtime is exercised separately under an explicit
budget in the DDE-068 end-to-end evidence run.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from uuid import uuid4

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from engine.capabilities.browser import (  # noqa: E402
    BrowserCaptureResult,
    BrowserCaptureSpec,
    BrowserProbeResult,
    BrowserProbeSpec,
)
from engine.capabilities.visual_critic import (  # noqa: E402
    VisualCritiqueRequest,
    VisualCritiqueResult,
)
from engine.context.repo import repo_root  # noqa: E402
from engine.missions.attempts import TaskAttemptService  # noqa: E402
from engine.verification.checks import CheckSpec  # noqa: E402
from engine.verification.oracle import AcceptanceOracleService  # noqa: E402
from engine.verification.runner import VerificationRunnerService  # noqa: E402
from engine.verification.visual_critique import DIMENSION_KEYS  # noqa: E402
from engine.workspaces.service import WorkspaceService  # noqa: E402
from tests.support.db import new_engine  # noqa: E402
from tests.support.verification_fixtures import (  # noqa: E402
    build_verification_fixture,
)


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (320, 200), color="white").save(buf, format="PNG")
    return buf.getvalue()


class _Browser:
    async def probe(self, spec: BrowserProbeSpec) -> BrowserProbeResult:
        del spec
        return BrowserProbeResult(
            exit_code=0, stdout="", stderr="", duration_ms=1, timed_out=False
        )

    async def screenshot(self, spec: BrowserCaptureSpec) -> BrowserCaptureResult:
        del spec
        return BrowserCaptureResult(
            exit_code=0, png_bytes=_png(), stderr="", duration_ms=1, timed_out=False
        )


class _Critic:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    async def critique(self, request: VisualCritiqueRequest) -> VisualCritiqueResult:
        del request
        return VisualCritiqueResult(
            exit_code=0,
            verdict_json=json.dumps(self.payload),
            stderr="",
            duration_ms=5,
            timed_out=False,
            cost_usd=0.19,
            model="stand-in-critic",
        )


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "verdict": "PASS",
        "confidence": 0.92,
        "dimension_scores": {key: 5 for key in DIMENSION_KEYS},
        "blocking_defects": [],
        "non_blocking_defects": [],
        "repair_instructions": [],
        "summary": "Meets the rubric.",
    }
    payload.update(overrides)
    return payload


def _outcome() -> CheckSpec:
    return CheckSpec(
        outcome_id=uuid4(),
        statement="rendered screen meets the visual rubric",
        kind="visual_critique",
        ref="critique:overview",
        command=["https://example.invalid/overview"],
    )


async def _run_gate(tmp_path: Path, *, slug: str, payload: dict[str, object], key: str):
    root = repo_root()
    db_engine = new_engine()
    workspace = None
    try:
        fixture = await build_verification_fixture(
            db_engine, tmp_path, mission_slug=slug
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(db_engine, root=root)
        oracle = await AcceptanceOracleService(db_engine).define(
            task=fixture.task, outcomes=[_outcome()], minimum_confidence=1.0
        )
        runner = VerificationRunnerService(
            db_engine,
            workspaces,
            browser=_Browser(),
            visual_critic=_Critic(payload),
        )
        run = await runner.run(
            task=fixture.task,
            worker_run=fixture.worker_run,
            workspace=fixture.workspace,
            oracle=oracle,
            idempotency_key=key,
        )
        attempt = await TaskAttemptService(db_engine).get_attempt(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            attempt_id=fixture.worker_run.task_attempt_id,
        )
        return run, attempt
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(workspace=workspace)
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_rubric_blocked_candidate_cannot_reach_completed(
    tmp_path: Path,
) -> None:
    """A screen the critic blocks on believable density never reaches a
    merged/COMPLETED state -- the charter's own acceptance criterion for
    the density floor, machine-enforced."""
    scores = {key: 5 for key in DIMENSION_KEYS}
    scores["believable_density"] = 2
    run, attempt = await _run_gate(
        tmp_path,
        slug="MISSION-CRITIQUE-BLOCK",
        payload=_payload(
            verdict="BLOCK",
            dimension_scores=scores,
            blocking_defects=[
                {
                    "dimension": "believable_density",
                    "detail": "Placeholder filler; hierarchy cannot be judged.",
                }
            ],
            repair_instructions=["Replace filler with realistic sample data."],
        ),
        key="verification-run-critique-block-1",
    )
    assert run.status == "FAILED"
    assert run.check_results[0].kind == "visual_critique"
    assert run.check_results[0].status == "FAILED"
    assert attempt.status == "FAILED"
    assert attempt.failure_class == "VERIFICATION_FAILURE"


@pytest.mark.asyncio
async def test_rubric_passing_candidate_is_promoted(tmp_path: Path) -> None:
    run, attempt = await _run_gate(
        tmp_path,
        slug="MISSION-CRITIQUE-PASS",
        payload=_payload(),
        key="verification-run-critique-pass-1",
    )
    assert run.status == "PASSED"
    assert attempt.status == "COMPLETED"


@pytest.mark.asyncio
async def test_unusable_critic_response_does_not_promote(tmp_path: Path) -> None:
    """Infrastructure failure is not approval: a malformed verdict makes the
    run ERRORED, and an ERRORED run never finalises the attempt."""
    run, attempt = await _run_gate(
        tmp_path,
        slug="MISSION-CRITIQUE-ERROR",
        payload={"verdict": "PASS"},  # missing every other required field
        key="verification-run-critique-error-1",
    )
    assert run.status == "ERRORED"
    assert attempt.status != "COMPLETED"
