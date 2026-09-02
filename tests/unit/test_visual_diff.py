"""DDE-044 pixel evidence + DDE-068 rendered-quality integration proofs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.capabilities.browser import (
    BrowserCaptureResult,
    BrowserCaptureSpec,
    BrowserLayoutBlock,
    BrowserLayoutResult,
    BrowserLayoutSpec,
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
_PNG_WHITE = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c49444154789c6360080000000200014a5c1bb40000000049454e44ae426082"
)


class _CaptureProbe:
    def __init__(
        self,
        png: bytes = _PNG_BLACK,
        *,
        layout: BrowserLayoutResult | None = None,
    ) -> None:
        self.png = png
        self.calls: list[BrowserCaptureSpec] = []
        self.layout_calls: list[BrowserLayoutSpec] = []
        self._layout = layout or _good_layout()

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

    async def layout(self, spec: BrowserLayoutSpec) -> BrowserLayoutResult:
        self.layout_calls.append(spec)
        return self._layout


def _good_layout() -> BrowserLayoutResult:
    blocks = (
        BrowserLayoutBlock("header", "", "Orders", 20, 20, 300, 60, False),
        BrowserLayoutBlock("section", "", "Open orders", 30, 120, 420, 150, False),
        BrowserLayoutBlock(
            "table",
            "",
            "Order status owner amount",
            30,
            300,
            700,
            250,
            False,
        ),
        BrowserLayoutBlock("button", "", "Create order", 760, 40, 140, 40, True),
        BrowserLayoutBlock("a", "", "View details", 760, 110, 120, 32, True),
    )
    return BrowserLayoutResult(
        exit_code=0,
        blocks=blocks,
        body_text=(
            "Orders Open orders assigned to your team. Order status owner amount "
            "updated destination priority customer reference. Create order "
            "View details."
        ),
        active_motion_count=0,
        spatial_motion_count=0,
        duration_ms=2,
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
                "density_floor": 4,
            }
        ),
        encoding="utf-8",
    )
    spec = load_visual_diff_spec(path)
    assert spec.url.startswith("file://")
    assert spec.golden_path.endswith("screen.png")
    assert spec.viewport_width == 900
    assert spec.max_diff_pixel_ratio == 0.02
    assert spec.quality_gate is True
    assert spec.density_floor == 4


def test_compare_pngs_byte_identical_passes() -> None:
    result = compare_pngs(
        actual=_PNG_BLACK,
        golden=_PNG_BLACK,
        max_diff_pixel_ratio=0.02,
    )
    assert result.passed is True
    assert result.diff_ratio == 0.0


def test_compare_pngs_exact_mode_fails_on_mismatch() -> None:
    result = compare_pngs(
        actual=_PNG_BLACK,
        golden=_PNG_WHITE,
        max_diff_pixel_ratio=0.0,
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
                "quality_gate": False,
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
    assert payload["quality_gate"] is False
    assert Path(tmp_path / payload["actual_path"]).is_file()
    assert len(probe.calls) == 1


@pytest.mark.asyncio
async def test_visual_diff_quality_gate_uses_normal_and_reduced_layouts(
    tmp_path: Path,
) -> None:
    visual_dir = tmp_path / "visual"
    golden_dir = visual_dir / "goldens"
    golden_dir.mkdir(parents=True)
    (golden_dir / "screen.png").write_bytes(_PNG_BLACK)
    (visual_dir / "screen.json").write_text(
        json.dumps(
            {
                "url": "https://example.invalid/",
                "golden_path": "visual/goldens/screen.png",
                "max_diff_pixel_ratio": 0.02,
                "quality_gate": True,
                "silhouette_threshold": 1.0,
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
            statement="screen is polished",
            kind="visual_diff",
            ref="visual:quality",
            command=["visual/screen.json"],
        ),
        browser=probe,
    )
    assert result.status == "PASSED"
    payload = json.loads(result.stdout)
    assert payload["quality"]["density_score"] >= 4
    assert [call.reduced_motion for call in probe.layout_calls] == [False, True]


@pytest.mark.asyncio
async def test_visual_diff_quality_gate_blocks_low_density(tmp_path: Path) -> None:
    visual_dir = tmp_path / "visual"
    golden_dir = visual_dir / "goldens"
    golden_dir.mkdir(parents=True)
    (golden_dir / "screen.png").write_bytes(_PNG_BLACK)
    (visual_dir / "screen.json").write_text(
        json.dumps(
            {
                "url": "https://example.invalid/",
                "golden_path": "visual/goldens/screen.png",
                "max_diff_pixel_ratio": 0.02,
                "quality_gate": True,
            }
        ),
        encoding="utf-8",
    )
    sparse = BrowserLayoutResult(
        exit_code=0,
        blocks=(BrowserLayoutBlock("p", "", "Item 1", 10, 10, 60, 20, False),),
        body_text="Item 1",
        active_motion_count=0,
        spatial_motion_count=0,
        duration_ms=1,
        timed_out=False,
    )
    result = await run_check(
        workspaces=None,  # type: ignore[arg-type]
        workspace=_workspace(tmp_path),
        spec=CheckSpec(
            outcome_id=uuid7(),
            statement="screen is polished",
            kind="visual_diff",
            ref="visual:quality",
            command=["visual/screen.json"],
        ),
        browser=_CaptureProbe(png=_PNG_BLACK, layout=sparse),
    )
    assert result.status == "FAILED"
    payload = json.loads(result.stdout)
    assert "believable_density_below_floor" in payload["quality"]["failures"]


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
                "quality_gate": False,
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
