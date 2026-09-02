"""Chapter 11.2 `visual_diff` binding — workspace JSON spec.

DDE-044 introduced deterministic screenshot/golden comparison. DDE-068
extends the same rendered evidence request with hard Definition-of-Polished
thresholds: believable density, generic-silhouette distance, and
reduced-motion end-state preservation. Keeping these settings on the same
workspace spec means the screenshot and the hard quality verdict are pinned
to one URL, viewport and evidence lineage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.core.errors import DdeError

DEFAULT_MAX_DIFF_PIXEL_RATIO = 0.02
DEFAULT_VIEWPORT_WIDTH = 1280
DEFAULT_VIEWPORT_HEIGHT = 720
DEFAULT_DENSITY_FLOOR = 4
DEFAULT_SILHOUETTE_THRESHOLD = 0.94
DEFAULT_REDUCED_MOTION_END_STATE_SIMILARITY = 0.98


@dataclass(frozen=True)
class VisualDiffSpec:
    """One deterministic rendered visual check."""

    url: str
    golden_path: str
    viewport_width: int = DEFAULT_VIEWPORT_WIDTH
    viewport_height: int = DEFAULT_VIEWPORT_HEIGHT
    max_diff_pixel_ratio: float = DEFAULT_MAX_DIFF_PIXEL_RATIO
    expect_text: str | None = None
    actual_path: str | None = None
    diff_path: str | None = None
    quality_gate: bool = True
    density_floor: int = DEFAULT_DENSITY_FLOOR
    silhouette_threshold: float = DEFAULT_SILHOUETTE_THRESHOLD
    reduced_motion_end_state_similarity: float = (
        DEFAULT_REDUCED_MOTION_END_STATE_SIMILARITY
    )


def load_visual_diff_spec(path: Path) -> VisualDiffSpec:
    if not path.is_file():
        raise DdeError(
            "POLICY_DENIED",
            "visual_diff spec file is missing",
            details={"path": str(path)},
        )
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DdeError(
            "POLICY_DENIED",
            "visual_diff spec is not valid JSON",
            details={"path": str(path), "error": str(exc)},
        ) from exc
    if not isinstance(raw, dict):
        raise DdeError(
            "POLICY_DENIED",
            "visual_diff spec must be a JSON object",
            details={"path": str(path)},
        )
    url = raw.get("url")
    golden = raw.get("golden_path")
    if not isinstance(url, str) or not url:
        raise DdeError(
            "POLICY_DENIED",
            "visual_diff.spec requires a non-empty string url",
            details={"path": str(path)},
        )
    if not isinstance(golden, str) or not golden:
        raise DdeError(
            "POLICY_DENIED",
            "visual_diff.spec requires a non-empty string golden_path",
            details={"path": str(path)},
        )
    viewport = raw.get("viewport") or {}
    if not isinstance(viewport, dict):
        raise DdeError(
            "POLICY_DENIED",
            "visual_diff.spec viewport must be an object",
            details={"path": str(path)},
        )
    width = int(viewport.get("width", DEFAULT_VIEWPORT_WIDTH))
    height = int(viewport.get("height", DEFAULT_VIEWPORT_HEIGHT))
    if width <= 0 or height <= 0:
        raise DdeError(
            "POLICY_DENIED",
            "visual_diff viewport dimensions must be positive",
            details={"width": width, "height": height},
        )
    ratio = float(raw.get("max_diff_pixel_ratio", DEFAULT_MAX_DIFF_PIXEL_RATIO))
    if not (0.0 <= ratio <= 1.0):
        raise DdeError(
            "POLICY_DENIED",
            "max_diff_pixel_ratio must be within [0, 1]",
            details={"max_diff_pixel_ratio": ratio},
        )
    expect = raw.get("expect_text")
    if expect is not None and not isinstance(expect, str):
        raise DdeError(
            "POLICY_DENIED",
            "expect_text must be a string when present",
            details={"path": str(path)},
        )
    actual = raw.get("actual_path")
    diff = raw.get("diff_path")
    quality_gate = raw.get("quality_gate", True)
    if not isinstance(quality_gate, bool):
        raise DdeError(
            "POLICY_DENIED",
            "quality_gate must be boolean",
            details={"path": str(path)},
        )
    density_floor = int(raw.get("density_floor", DEFAULT_DENSITY_FLOOR))
    if not (0 <= density_floor <= 5):
        raise DdeError(
            "POLICY_DENIED",
            "density_floor must be within [0, 5]",
            details={"density_floor": density_floor},
        )
    silhouette_threshold = float(
        raw.get("silhouette_threshold", DEFAULT_SILHOUETTE_THRESHOLD)
    )
    end_state_similarity = float(
        raw.get(
            "reduced_motion_end_state_similarity",
            DEFAULT_REDUCED_MOTION_END_STATE_SIMILARITY,
        )
    )
    for name, value in (
        ("silhouette_threshold", silhouette_threshold),
        ("reduced_motion_end_state_similarity", end_state_similarity),
    ):
        if not (0.0 <= value <= 1.0):
            raise DdeError(
                "POLICY_DENIED",
                f"{name} must be within [0, 1]",
                details={name: value},
            )
    return VisualDiffSpec(
        url=url,
        golden_path=golden,
        viewport_width=width,
        viewport_height=height,
        max_diff_pixel_ratio=ratio,
        expect_text=expect,
        actual_path=actual if isinstance(actual, str) else None,
        diff_path=diff if isinstance(diff, str) else None,
        quality_gate=quality_gate,
        density_floor=density_floor,
        silhouette_threshold=silhouette_threshold,
        reduced_motion_end_state_similarity=end_state_similarity,
    )
