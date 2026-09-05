"""DDE-044 visual_diff pixel evidence proofs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.capabilities.browser import (
    BrowserCaptureResult,
    BrowserCaptureSpec,
    BrowserProbeResult,
    BrowserProbeSpec,
)
from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.verification.checks import CheckSpec, run_check
from engine.verification.pixel_compare import compare_pngs
from engine.verification.visual_spec import load_visual_diff_spec

# Minimal valid 1x1 PNG (black pixel).
_PNG_BLACK = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)
# Distinct 1x1 PNG (white) produced via pillow when available; else skip ratio tests.
_PNG_WHITE = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c49444154789c6360080000000200014a5c1bb40000000049454e44ae426082"
)


class _CaptureProbe:
    def __init__(self, png: bytes = _PNG_BLACK) -> None:
        self.png = png
        self.calls: list[BrowserCaptureSpec] = []

    async def probe(self, spec: BrowserProbeSpec) -> BrowserProbeResult:
        del spec
        return BrowserProbeResult(
            exit_code=0, stdout="", stderr="", duration_ms=1, timed_out=False
        )

    async def screenshot(self, spec: BrowserCaptureSpec) -> BrowserCaptureResult:
        self.calls.append(spec)
        return BrowserCaptureResult(
            exit_code=0,
            png_bytes=self.png,
            stderr="",
            duration_ms=1,
            timed_out=False,
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


def test_load_visual_diff_spec_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "visual" / "screen.json"
    path.parent.mkdir()
    path.write_text(
        json.dumps(
            {
                "url": "file:///tmp/x.html",
                "golden_path": "visual/goldens/screen.png",
                "viewport": {"width": 900, "height": 600},
                "max_diff_pixel_ratio": 0.02,
            }
        ),
        encoding="utf-8",
    )
    spec = load_visual_diff_spec(path)
    assert spec.url.startswith("file://")
    assert spec.golden_path.endswith("screen.png")
    assert spec.viewport_width == 900
    assert spec.max_diff_pixel_ratio == 0.02


def test_compare_pngs_byte_identical_passes() -> None:
    result = compare_pngs(
        actual=_PNG_BLACK, golden=_PNG_BLACK, max_diff_pixel_ratio=0.02
    )
    assert result.passed is True
    assert result.diff_ratio == 0.0


def test_compare_pngs_exact_mode_fails_on_mismatch() -> None:
    result = compare_pngs(
        actual=_PNG_BLACK, golden=_PNG_WHITE, max_diff_pixel_ratio=0.0
    )
    assert result.passed is False


@pytest.mark.asyncio
async def test_visual_diff_check_passes_on_matching_golden(tmp_path: Path) -> None:
    visual_dir = tmp_path / "visual"
    golden_dir = visual_dir / "goldens"
    golden_dir.mkdir(parents=True)
    golden = golden_dir / "screen.png"
    golden.write_bytes(_PNG_BLACK)
    spec_path = visual_dir / "supplier-credit-screen.json"
    spec_path.write_text(
        json.dumps(
            {
                "url": "https://example.invalid/",
                "golden_path": "visual/goldens/screen.png",
                "max_diff_pixel_ratio": 0.02,
            }
        ),
        encoding="utf-8",
    )
    probe = _CaptureProbe(png=_PNG_BLACK)
    result = await run_check(
        workspaces=None,  # type: ignore[arg-type]
        workspace=_workspace(tmp_path),
        spec=CheckSpec(
            outcome_id=uuid7(),
            statement="credit screen matches golden",
            kind="visual_diff",
            ref="visual:credit",
            command=["visual/supplier-credit-screen.json"],
        ),
        browser=probe,
    )
    assert result.status == "PASSED"
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["diff_ratio"] == 0.0
    assert Path(tmp_path / payload["actual_path"]).is_file()
    assert len(probe.calls) == 1


@pytest.mark.asyncio
async def test_visual_diff_check_fails_on_mismatch(tmp_path: Path) -> None:
    visual_dir = tmp_path / "visual"
    golden_dir = visual_dir / "goldens"
    golden_dir.mkdir(parents=True)
    (golden_dir / "screen.png").write_bytes(_PNG_BLACK)
    (visual_dir / "screen.json").write_text(
        json.dumps(
            {
                "url": "https://example.invalid/",
                "golden_path": "visual/goldens/screen.png",
                "max_diff_pixel_ratio": 0.0,
            }
        ),
        encoding="utf-8",
    )
    result = await run_check(
        workspaces=None,  # type: ignore[arg-type]
        workspace=_workspace(tmp_path),
        spec=CheckSpec(
            outcome_id=uuid7(),
            statement="must match",
            kind="visual_diff",
            ref="visual:x",
            command=["visual/screen.json"],
        ),
        browser=_CaptureProbe(png=_PNG_WHITE),
    )
    assert result.status == "FAILED"
    assert result.exit_code == 1


@pytest.mark.asyncio
async def test_visual_diff_fails_closed_without_browser(tmp_path: Path) -> None:
    with pytest.raises(DdeError) as exc:
        await run_check(
            workspaces=None,  # type: ignore[arg-type]
            workspace=_workspace(tmp_path),
            spec=CheckSpec(
                outcome_id=uuid7(),
                statement="x",
                kind="visual_diff",
                ref="visual:x",
                command=["visual/x.json"],
            ),
            browser=None,
        )
    assert exc.value.error_code == "POLICY_DENIED"


@pytest.mark.asyncio
async def test_visual_diff_can_bind_runtime_candidate_url_without_mutating_spec(
    tmp_path: Path,
) -> None:
    visual_dir = tmp_path / "visual"
    golden_dir = visual_dir / "goldens"
    golden_dir.mkdir(parents=True)
    (golden_dir / "screen.png").write_bytes(_PNG_BLACK)
    (visual_dir / "screen.json").write_text(
        json.dumps(
            {
                "url": "file:///accepted/screen.html",
                "golden_path": "visual/goldens/screen.png",
                "viewport": {"width": 900, "height": 600},
                "max_diff_pixel_ratio": 0.02,
            }
        ),
        encoding="utf-8",
    )
    probe = _CaptureProbe()
    spec = CheckSpec(
        outcome_id=uuid7(),
        statement="candidate matches golden",
        kind="visual_diff",
        ref="screens/x:visual_diff",
        command=["visual/screen.json"],
    )
    result = await run_check(
        workspaces=None,  # type: ignore[arg-type] - visual_diff never executes shell
        workspace=_workspace(tmp_path),
        spec=spec,
        browser=probe,
        render_url_override="file:///candidate/.dde/preview/current.html",
    )
    assert result.status == "PASSED"
    assert probe.calls[0].url == "file:///candidate/.dde/preview/current.html"
    assert json.loads(result.stdout)["render_url"] == probe.calls[0].url
    assert load_visual_diff_spec(visual_dir / "screen.json").url == (
        "file:///accepted/screen.html"
    )
