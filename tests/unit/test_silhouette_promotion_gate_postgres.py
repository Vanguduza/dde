"""DDE-068 promotion-gate proof: the silhouette check kind is not a parallel
system bolted onto DDE's verification chain -- it is one more
`EXECUTABLE_KINDS` member, so it is *already* consumed by the real,
pre-existing production promotion path with zero additional wiring:

    `VerificationRunnerService.run()`
        -> `_execute_outcome()` (calls `engine.verification.checks.run_check`)
        -> `_evaluate()` (kind-agnostic: reads only `CheckResult.status`)
        -> `_finalise_passed_attempt()` / `_fail_unverified_attempt()`
        -> `TaskAttemptService.finalize()` / `.fail()`

This is DDE-068's charter item 10 ("a real promotion/merge/quality gate
that consumes the recorded visual verdict") and its acceptance criterion
("A generated screen that fails ... CANNOT reach a merged state"), proven
end-to-end against a real Postgres-backed `VerificationRun`/`TaskAttempt`,
not a unit-level mock of the gate.
"""

from __future__ import annotations

import io
from pathlib import Path
from uuid import uuid4

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image, ImageDraw  # noqa: E402

from engine.capabilities.browser import (  # noqa: E402
    BrowserCaptureResult,
    BrowserCaptureSpec,
    BrowserProbeResult,
    BrowserProbeSpec,
)
from engine.context.repo import repo_root  # noqa: E402
from engine.missions.attempts import TaskAttemptService  # noqa: E402
from engine.verification.checks import CheckSpec  # noqa: E402
from engine.verification.oracle import AcceptanceOracleService  # noqa: E402
from engine.verification.runner import VerificationRunnerService  # noqa: E402
from engine.verification.silhouette import GRID_COLS, GRID_ROWS  # noqa: E402
from engine.workspaces.service import WorkspaceService  # noqa: E402
from tests.support.db import new_engine  # noqa: E402
from tests.support.verification_fixtures import build_verification_fixture  # noqa: E402

_WIDTH = 1200
_HEIGHT = 800
_CELL_W = _WIDTH // GRID_COLS
_CELL_H = _HEIGHT // GRID_ROWS


def _render(rows: tuple[str, ...]) -> bytes:
    image = Image.new("RGB", (_WIDTH, _HEIGHT), color="white")
    draw = ImageDraw.Draw(image)
    for row_index, row in enumerate(rows):
        for col_index, char in enumerate(row):
            if char != "#":
                continue
            x0 = col_index * _CELL_W
            y0 = row_index * _CELL_H
            draw.rectangle([x0, y0, x0 + _CELL_W - 1, y0 + _CELL_H - 1], fill="black")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


#: Same self-generated "centered-hero-3-card" template as
#: `engine.verification.silhouette.GENERIC_LAYOUT_CORPUS` -- a screen that
#: renders this IS the generic layout the gate exists to catch.
_GENERIC_LAYOUT_PNG = _render(
    (
        "..########..",
        "..########..",
        "............",
        "###.###.###.",
        "###.###.###.",
        "###.###.###.",
        "............",
        "............",
    )
)

_DISTINCTIVE_LAYOUT_PNG = _render(
    (
        "............",
        "............",
        "............",
        "............",
        "............",
        "............",
        "........#...",
        "............",
    )
)


class _CaptureProbe:
    def __init__(self, png: bytes) -> None:
        self.png = png

    async def probe(self, spec: BrowserProbeSpec) -> BrowserProbeResult:
        del spec
        return BrowserProbeResult(
            exit_code=0, stdout="", stderr="", duration_ms=1, timed_out=False
        )

    async def screenshot(self, spec: BrowserCaptureSpec) -> BrowserCaptureResult:
        del spec
        return BrowserCaptureResult(
            exit_code=0, png_bytes=self.png, stderr="", duration_ms=1, timed_out=False
        )


@pytest.mark.asyncio
async def test_generic_layout_silhouette_blocks_task_attempt_promotion(
    tmp_path: Path,
) -> None:
    """A screen whose rendered silhouette near-matches the self-generated
    generic-layout corpus produces a real FAILED `VerificationRun` and a
    real FAILED `TaskAttempt` -- it cannot reach `COMPLETED`. This is the
    playbook §10.3 "near-match = review blocker" rule proven through the
    actual production promotion path, not asserted against the check
    result in isolation."""
    root = repo_root()
    db_engine = new_engine()
    workspace = None
    try:
        fixture = await build_verification_fixture(
            db_engine, tmp_path, mission_slug="MISSION-SILHOUETTE-BLOCK"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(db_engine, root=root)

        silhouette_outcome = CheckSpec(
            outcome_id=uuid4(),
            statement="rendered screen is not a generic-layout near-match",
            kind="silhouette",
            ref="silhouette:overview",
            command=["https://example.invalid/overview"],
        )
        oracles = AcceptanceOracleService(db_engine)
        oracle = await oracles.define(
            task=fixture.task, outcomes=[silhouette_outcome], minimum_confidence=1.0
        )

        runner = VerificationRunnerService(
            db_engine, workspaces, browser=_CaptureProbe(png=_GENERIC_LAYOUT_PNG)
        )
        run = await runner.run(
            task=fixture.task,
            worker_run=fixture.worker_run,
            workspace=fixture.workspace,
            oracle=oracle,
            idempotency_key="verification-run-silhouette-block-1",
        )

        assert run.status == "FAILED"
        assert run.confidence == 0.0
        failed_check = run.check_results[0]
        assert failed_check.kind == "silhouette"
        assert failed_check.status == "FAILED"

        attempt = await TaskAttemptService(db_engine).get_attempt(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            attempt_id=fixture.worker_run.task_attempt_id,
        )
        assert attempt.status == "FAILED"
        assert attempt.failure_class == "VERIFICATION_FAILURE"
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(workspace=workspace)
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_distinctive_layout_silhouette_allows_task_attempt_promotion(
    tmp_path: Path,
) -> None:
    """The converse proof: a screen whose silhouette does NOT near-match
    the generic-layout corpus passes, and the task attempt is allowed to
    reach `COMPLETED` -- a good candidate is not held back by the gate."""
    root = repo_root()
    db_engine = new_engine()
    workspace = None
    try:
        fixture = await build_verification_fixture(
            db_engine, tmp_path, mission_slug="MISSION-SILHOUETTE-PASS"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(db_engine, root=root)

        silhouette_outcome = CheckSpec(
            outcome_id=uuid4(),
            statement="rendered screen is not a generic-layout near-match",
            kind="silhouette",
            ref="silhouette:overview",
            command=["https://example.invalid/overview"],
        )
        oracles = AcceptanceOracleService(db_engine)
        oracle = await oracles.define(
            task=fixture.task, outcomes=[silhouette_outcome], minimum_confidence=1.0
        )

        runner = VerificationRunnerService(
            db_engine, workspaces, browser=_CaptureProbe(png=_DISTINCTIVE_LAYOUT_PNG)
        )
        run = await runner.run(
            task=fixture.task,
            worker_run=fixture.worker_run,
            workspace=fixture.workspace,
            oracle=oracle,
            idempotency_key="verification-run-silhouette-pass-1",
        )

        assert run.status == "PASSED"
        assert run.confidence == 1.0

        attempt = await TaskAttemptService(db_engine).get_attempt(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            attempt_id=fixture.worker_run.task_attempt_id,
        )
        assert attempt.status == "COMPLETED"
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(workspace=workspace)
        await db_engine.dispose()
