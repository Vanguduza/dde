"""Pixel compare for visual_diff goldens (DDE-044).

Chapter 9.6 admission for optional `pillow` (when max_diff_pixel_ratio > 0
and the PNGs are not byte-identical):
- Package: `pillow` (HPND — permissive, OSI-recognized)
- Maintenance: actively maintained; de-facto Python imaging stdlib substitute
- Why stdlib is insufficient: Python has no PNG decoder or pixel buffer API.

Exact byte equality always passes without Pillow. Studio Phase-B
(EDR-0008) uses maxDiffPixelRatio 0.02; that path needs Pillow.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from engine.core.errors import DdeError


@dataclass(frozen=True)
class PixelCompareResult:
    passed: bool
    diff_ratio: float
    diff_png: bytes | None
    detail: str


def compare_pngs(
    *,
    actual: bytes,
    golden: bytes,
    max_diff_pixel_ratio: float,
) -> PixelCompareResult:
    if not actual:
        return PixelCompareResult(
            passed=False, diff_ratio=1.0, diff_png=None, detail="actual PNG is empty"
        )
    if not golden:
        return PixelCompareResult(
            passed=False, diff_ratio=1.0, diff_png=None, detail="golden PNG is empty"
        )
    if actual == golden:
        return PixelCompareResult(
            passed=True, diff_ratio=0.0, diff_png=None, detail="byte-identical"
        )
    if max_diff_pixel_ratio <= 0.0:
        return PixelCompareResult(
            passed=False,
            diff_ratio=1.0,
            diff_png=None,
            detail="PNGs differ and max_diff_pixel_ratio is 0 (exact match required)",
        )
    try:
        from PIL import Image, ImageChops  # type: ignore[import-not-found]
    except ImportError as exc:
        raise DdeError(
            "POLICY_DENIED",
            "pillow is required for non-exact visual_diff; install the "
            "optional 'browser' extra (HPND, Chapter 9.6)",
            details={"dependency": "pillow"},
        ) from exc

    actual_img = Image.open(io.BytesIO(actual)).convert("RGBA")
    golden_img = Image.open(io.BytesIO(golden)).convert("RGBA")
    if actual_img.size != golden_img.size:
        return PixelCompareResult(
            passed=False,
            diff_ratio=1.0,
            diff_png=None,
            detail=(f"size mismatch actual={actual_img.size} golden={golden_img.size}"),
        )
    diff = ImageChops.difference(actual_img, golden_img)
    bbox_data = list(diff.getdata())
    changed = sum(1 for pixel in bbox_data if pixel[0] or pixel[1] or pixel[2])
    total = actual_img.size[0] * actual_img.size[1]
    ratio = (changed / total) if total else 1.0
    buf = io.BytesIO()
    diff.save(buf, format="PNG")
    return PixelCompareResult(
        passed=ratio <= max_diff_pixel_ratio,
        diff_ratio=ratio,
        diff_png=buf.getvalue(),
        detail=f"diff_ratio={ratio:.6f} threshold={max_diff_pixel_ratio}",
    )
