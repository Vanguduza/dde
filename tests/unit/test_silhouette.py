"""DDE-068 silhouette-distinctiveness gate proofs (playbook §10.3).

Synthetic PNGs are drawn (not scraped/donor) so the corpus-provenance law
(EDR-0016 decision 6: self-generated, license-clean) extends to the tests
themselves.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image, ImageDraw  # noqa: E402

from engine.capabilities.browser import (  # noqa: E402
    BrowserCaptureResult,
    BrowserCaptureSpec,
)
from engine.contracts.workspace import Workspace  # noqa: E402
from engine.core.errors import DdeError  # noqa: E402
from engine.core.ids import uuid7  # noqa: E402
from engine.verification.checks import CheckSpec, run_check  # noqa: E402
from engine.verification.oracle import (  # noqa: E402
    EXECUTABLE_KINDS,
    validate_definition,
)
from engine.verification.silhouette import (  # noqa: E402
    GRID_COLS,
    GRID_ROWS,
    compute_fingerprint,
    evaluate_silhouette,
)

_WIDTH = 1200
_HEIGHT = 800
_CELL_W = _WIDTH // GRID_COLS
_CELL_H = _HEIGHT // GRID_ROWS


def _render(rows: tuple[str, ...]) -> bytes:
    """Draw a white canvas with black cells wherever `rows` marks '#',
    matching the same GRID_COLS x GRID_ROWS convention as the corpus
    templates in `engine.verification.silhouette`."""
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


_THREE_CARD_PNG = _render(
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

_DISTINCT_PNG = _render(
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


def _blank_png() -> bytes:
    image = Image.new("RGB", (_WIDTH, _HEIGHT), color="white")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_silhouette_is_an_executable_oracle_kind() -> None:
    assert "silhouette" in EXECUTABLE_KINDS
    validate_definition(
        scope="task",
        observable_outcomes=[
            CheckSpec(
                outcome_id=uuid7(),
                statement="screen is visually distinctive",
                kind="silhouette",
                ref="silhouette:home",
                command=["https://example.invalid/"],
            )
        ],
        negative_cases=[],
        minimum_confidence=1.0,
    )


def test_compute_fingerprint_is_deterministic() -> None:
    first = compute_fingerprint(_THREE_CARD_PNG)
    second = compute_fingerprint(_THREE_CARD_PNG)
    assert first.fingerprint_hash == second.fingerprint_hash
    assert first.occupancy == second.occupancy


def test_three_card_layout_matches_corpus_and_blocks() -> None:
    verdict = evaluate_silhouette(_THREE_CARD_PNG)
    assert verdict.blocked is True
    assert verdict.matched_template == "centered-hero-3-card"
    assert verdict.similarity >= 0.85


def test_distinct_layout_does_not_block() -> None:
    verdict = evaluate_silhouette(_DISTINCT_PNG)
    assert verdict.blocked is False
    assert verdict.matched_template is None


def test_blank_render_does_not_false_positive_block() -> None:
    verdict = evaluate_silhouette(_blank_png())
    assert verdict.blocked is False


def test_compute_fingerprint_rejects_empty_bytes() -> None:
    with pytest.raises(DdeError) as exc:
        compute_fingerprint(b"")
    assert exc.value.error_code == "POLICY_DENIED"


class _CaptureProbe:
    def __init__(self, png: bytes) -> None:
        self.png = png
        self.calls: list[BrowserCaptureSpec] = []

    async def probe(self, spec):  # pragma: no cover - unused by silhouette
        raise NotImplementedError

    async def screenshot(self, spec: BrowserCaptureSpec) -> BrowserCaptureResult:
        self.calls.append(spec)
        return BrowserCaptureResult(
            exit_code=0, png_bytes=self.png, stderr="", duration_ms=1, timed_out=False
        )


def _workspace(tmp_path: Path) -> Workspace:
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    return Workspace(
        workspace_id=uuid7(),
        tenant_id=uuid7(),
        project_id=uuid7(),
        mission_id=uuid7(),
        task_id=uuid7(),
        execution_environment_id=uuid7(),
        base_revision="HEAD",
        current_revision="HEAD",
        workspace_path=str(tmp_path),
        policy={},
        status="READY",
        lock_version=1,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_silhouette_check_fails_closed_on_generic_layout(tmp_path: Path) -> None:
    probe = _CaptureProbe(png=_THREE_CARD_PNG)
    result = await run_check(
        workspaces=None,  # type: ignore[arg-type]
        workspace=_workspace(tmp_path),
        spec=CheckSpec(
            outcome_id=uuid7(),
            statement="screen is visually distinctive",
            kind="silhouette",
            ref="silhouette:overview",
            command=["https://example.invalid/overview"],
        ),
        browser=probe,
    )
    assert result.status == "FAILED"
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["blocked"] is True
    assert payload["matched_template"] == "centered-hero-3-card"
    assert len(probe.calls) == 1


@pytest.mark.asyncio
async def test_silhouette_check_passes_on_distinctive_layout(tmp_path: Path) -> None:
    result = await run_check(
        workspaces=None,  # type: ignore[arg-type]
        workspace=_workspace(tmp_path),
        spec=CheckSpec(
            outcome_id=uuid7(),
            statement="screen is visually distinctive",
            kind="silhouette",
            ref="silhouette:overview",
            command=["https://example.invalid/overview"],
        ),
        browser=_CaptureProbe(png=_DISTINCT_PNG),
    )
    assert result.status == "PASSED"
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["blocked"] is False


@pytest.mark.asyncio
async def test_silhouette_fails_closed_without_browser(tmp_path: Path) -> None:
    with pytest.raises(DdeError) as exc:
        await run_check(
            workspaces=None,  # type: ignore[arg-type]
            workspace=_workspace(tmp_path),
            spec=CheckSpec(
                outcome_id=uuid7(),
                statement="x",
                kind="silhouette",
                ref="silhouette:x",
                command=["https://example.invalid/"],
            ),
            browser=None,
        )
    assert exc.value.error_code == "POLICY_DENIED"


@pytest.mark.asyncio
async def test_silhouette_requires_url_command(tmp_path: Path) -> None:
    with pytest.raises(DdeError) as exc:
        await run_check(
            workspaces=None,  # type: ignore[arg-type]
            workspace=_workspace(tmp_path),
            spec=CheckSpec(
                outcome_id=uuid7(),
                statement="x",
                kind="silhouette",
                ref="silhouette:x",
                command=[],
            ),
            browser=_CaptureProbe(png=_DISTINCT_PNG),
        )
    assert exc.value.error_code == "POLICY_DENIED"
