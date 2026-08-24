"""Chapter 11.2 `visual_diff` binding — workspace JSON spec (DDE-044).

Blueprint example ref: `visual/supplier-credit-screen.json`. The binding's
`command[0]` is the workspace-relative path to this JSON; the runner loads
it, captures a screenshot via `capability.browser`, and compares against
the golden PNG named here.

VLM critique / silhouette / Definition-of-Polished remain DDE-068.
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


@dataclass(frozen=True)
class VisualDiffSpec:
    """One deterministic pixel check.

    `url` is navigated under the browser allowlist. `golden_path` is a
    workspace-relative PNG. `max_diff_pixel_ratio` matches the studio
    Phase-B default (EDR-0008 / Playwright `maxDiffPixelRatio: 0.02`).
    """

    url: str
    golden_path: str
    viewport_width: int = DEFAULT_VIEWPORT_WIDTH
    viewport_height: int = DEFAULT_VIEWPORT_HEIGHT
    max_diff_pixel_ratio: float = DEFAULT_MAX_DIFF_PIXEL_RATIO
    expect_text: str | None = None
    actual_path: str | None = None
    diff_path: str | None = None


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
    return VisualDiffSpec(
        url=url,
        golden_path=golden,
        viewport_width=width,
        viewport_height=height,
        max_diff_pixel_ratio=ratio,
        expect_text=expect,
        actual_path=actual if isinstance(actual, str) else None,
        diff_path=diff if isinstance(diff, str) else None,
    )
