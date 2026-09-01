"""DDE-068 deterministic rendered visual-quality gates.

The input is `BrowserLayoutResult`, produced from the real rendered
ProductEnvironment by `capability.browser`. No model participates in these
verdicts. Density, generic-silhouette similarity, and reduced-motion
semantics are therefore hard gates: the later VLM `judge` and human pixel
sign-off may never turn one of these failures green.

The silhouette corpus is self-generated from the playbook's generic-layout
"nevers" (EDR-0016 accepted option (c)); it contains normalized rectangles,
not scraped third-party screenshots or design assets.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from engine.capabilities.browser import BrowserLayoutBlock, BrowserLayoutResult

GRID_COLUMNS: Final = 12
GRID_ROWS: Final = 8
DEFAULT_DENSITY_FLOOR: Final = 4
DEFAULT_SILHOUETTE_THRESHOLD: Final = 0.94
DEFAULT_END_STATE_SIMILARITY: Final = 0.98

_FILLER = re.compile(
    r"\blorem\s+ipsum\b|\bitem\s+\d+\b|\bcard\s+\d+\b|\bexample\s+\d+\b|"
    r"\bplaceholder\b|\bcoming\s+soon\b",
    re.I,
)
_STRUCTURAL_TAGS = frozenset(
    {
        "header",
        "nav",
        "section",
        "article",
        "aside",
        "footer",
        "form",
        "table",
    }
)

# Normalized x, y, width, height rectangles. These are generated internal
# abstractions of generic layout grammars, not copies of a third-party page.
_GENERIC_RECTANGLES: Final[
    dict[str, tuple[tuple[float, float, float, float], ...]]
] = {
    "centered_hero_three_cards": (
        (0.16, 0.08, 0.68, 0.28),
        (0.08, 0.48, 0.25, 0.30),
        (0.375, 0.48, 0.25, 0.30),
        (0.67, 0.48, 0.25, 0.30),
    ),
    "split_hero_three_cards": (
        (0.07, 0.08, 0.40, 0.32),
        (0.53, 0.08, 0.40, 0.32),
        (0.08, 0.52, 0.25, 0.28),
        (0.375, 0.52, 0.25, 0.28),
        (0.67, 0.52, 0.25, 0.28),
    ),
    "dashboard_stat_card_grid": (
        (0.03, 0.04, 0.16, 0.92),
        (0.23, 0.07, 0.22, 0.18),
        (0.48, 0.07, 0.22, 0.18),
        (0.73, 0.07, 0.22, 0.18),
        (0.23, 0.32, 0.46, 0.56),
        (0.72, 0.32, 0.23, 0.56),
    ),
}


@dataclass(frozen=True)
class SilhouetteMatch:
    corpus_id: str | None
    similarity: float
    fingerprint: str


@dataclass(frozen=True)
class VisualQualityAssessment:
    density_score: int
    density_floor: int
    occupied_ratio: float
    visible_blocks: int
    interactive_blocks: int
    word_count: int
    filler_detected: bool
    silhouette: SilhouetteMatch
    reduced_motion_spatial_count: int
    end_state_similarity: float
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures

    def as_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "density_score": self.density_score,
            "density_floor": self.density_floor,
            "occupied_ratio": round(self.occupied_ratio, 6),
            "visible_blocks": self.visible_blocks,
            "interactive_blocks": self.interactive_blocks,
            "word_count": self.word_count,
            "filler_detected": self.filler_detected,
            "silhouette": {
                "corpus_id": self.silhouette.corpus_id,
                "similarity": round(self.silhouette.similarity, 6),
                "fingerprint": self.silhouette.fingerprint,
            },
            "reduced_motion_spatial_count": self.reduced_motion_spatial_count,
            "end_state_similarity": round(self.end_state_similarity, 6),
            "failures": list(self.failures),
        }


def _cells_for_rect(
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    viewport_width: int,
    viewport_height: int,
) -> set[int]:
    if viewport_width <= 0 or viewport_height <= 0 or width <= 0 or height <= 0:
        return set()
    left = max(0.0, min(x / viewport_width, 1.0))
    top = max(0.0, min(y / viewport_height, 1.0))
    right = max(left, min((x + width) / viewport_width, 1.0))
    bottom = max(top, min((y + height) / viewport_height, 1.0))
    x0 = min(int(left * GRID_COLUMNS), GRID_COLUMNS - 1)
    y0 = min(int(top * GRID_ROWS), GRID_ROWS - 1)
    x1 = min(max(int(right * GRID_COLUMNS - 1e-9), x0), GRID_COLUMNS - 1)
    y1 = min(max(int(bottom * GRID_ROWS - 1e-9), y0), GRID_ROWS - 1)
    return {
        row * GRID_COLUMNS + col
        for row in range(y0, y1 + 1)
        for col in range(x0, x1 + 1)
    }


def _all_cells(
    blocks: tuple[BrowserLayoutBlock, ...],
    *,
    viewport_width: int,
    viewport_height: int,
) -> set[int]:
    cells: set[int] = set()
    for block in blocks:
        cells.update(
            _cells_for_rect(
                block.x,
                block.y,
                block.width,
                block.height,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
            )
        )
    return cells


def _structural_cells(
    blocks: tuple[BrowserLayoutBlock, ...],
    *,
    viewport_width: int,
    viewport_height: int,
) -> set[int]:
    viewport_area = max(viewport_width * viewport_height, 1)
    cells: set[int] = set()
    for block in blocks:
        area_ratio = (block.width * block.height) / viewport_area
        if block.tag not in _STRUCTURAL_TAGS or not (0.025 <= area_ratio <= 0.72):
            continue
        cells.update(
            _cells_for_rect(
                block.x,
                block.y,
                block.width,
                block.height,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
            )
        )
    return cells


def _corpus_cells(
    rectangles: tuple[tuple[float, float, float, float], ...],
) -> set[int]:
    cells: set[int] = set()
    for x, y, width, height in rectangles:
        cells.update(
            _cells_for_rect(
                x * GRID_COLUMNS,
                y * GRID_ROWS,
                width * GRID_COLUMNS,
                height * GRID_ROWS,
                viewport_width=GRID_COLUMNS,
                viewport_height=GRID_ROWS,
            )
        )
    return cells


def _jaccard(left: set[int], right: set[int]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    return (len(left & right) / len(union)) if union else 0.0


def _fingerprint(cells: set[int]) -> str:
    size = GRID_COLUMNS * GRID_ROWS
    return "".join("1" if index in cells else "0" for index in range(size))


def silhouette_match(
    layout: BrowserLayoutResult,
    *,
    viewport_width: int,
    viewport_height: int,
) -> SilhouetteMatch:
    actual = _structural_cells(
        layout.blocks,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
    )
    if not actual:
        return SilhouetteMatch(
            corpus_id=None,
            similarity=0.0,
            fingerprint=_fingerprint(actual),
        )
    best_id: str | None = None
    best = 0.0
    for corpus_id, rectangles in _GENERIC_RECTANGLES.items():
        similarity = _jaccard(actual, _corpus_cells(rectangles))
        if similarity > best:
            best = similarity
            best_id = corpus_id
    return SilhouetteMatch(
        corpus_id=best_id,
        similarity=best,
        fingerprint=_fingerprint(actual),
    )


def _density(
    layout: BrowserLayoutResult,
    *,
    viewport_width: int,
    viewport_height: int,
) -> tuple[int, float, int, int, int, bool]:
    visible = tuple(
        block for block in layout.blocks if block.width * block.height >= 16
    )
    interactive = sum(1 for block in visible if block.interactive)
    words = re.findall(r"\b[\w'-]+\b", layout.body_text)
    filler = bool(_FILLER.search(layout.body_text))
    occupied = len(
        _all_cells(
            visible,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )
    ) / (GRID_COLUMNS * GRID_ROWS)

    score = 0
    if len(visible) >= 4:
        score += 1
    if len(words) >= 12:
        score += 1
    if len(words) >= 24 or interactive >= 2:
        score += 1
    if 0.18 <= occupied <= 0.96:
        score += 1
    if not filler:
        score += 1
    return min(score, 5), occupied, len(visible), interactive, len(words), filler


def assess_visual_quality(
    normal: BrowserLayoutResult,
    reduced_motion: BrowserLayoutResult,
    *,
    viewport_width: int,
    viewport_height: int,
    density_floor: int = DEFAULT_DENSITY_FLOOR,
    silhouette_threshold: float = DEFAULT_SILHOUETTE_THRESHOLD,
    end_state_similarity_floor: float = DEFAULT_END_STATE_SIMILARITY,
) -> VisualQualityAssessment:
    """Return the hard DDE-068 verdict over two real rendered snapshots."""
    if normal.exit_code != 0 or normal.timed_out:
        return VisualQualityAssessment(
            density_score=0,
            density_floor=density_floor,
            occupied_ratio=0.0,
            visible_blocks=0,
            interactive_blocks=0,
            word_count=0,
            filler_detected=False,
            silhouette=SilhouetteMatch(None, 0.0, ""),
            reduced_motion_spatial_count=0,
            end_state_similarity=0.0,
            failures=("normal_layout_capture_failed",),
        )
    if reduced_motion.exit_code != 0 or reduced_motion.timed_out:
        return VisualQualityAssessment(
            density_score=0,
            density_floor=density_floor,
            occupied_ratio=0.0,
            visible_blocks=0,
            interactive_blocks=0,
            word_count=0,
            filler_detected=False,
            silhouette=SilhouetteMatch(None, 0.0, ""),
            reduced_motion_spatial_count=0,
            end_state_similarity=0.0,
            failures=("reduced_motion_layout_capture_failed",),
        )

    density, occupied, visible, interactive, words, filler = _density(
        normal,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
    )
    silhouette = silhouette_match(
        normal,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
    )
    normal_cells = _structural_cells(
        normal.blocks,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
    )
    reduced_cells = _structural_cells(
        reduced_motion.blocks,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
    )
    end_similarity = _jaccard(normal_cells, reduced_cells)

    failures: list[str] = []
    if density < density_floor:
        failures.append("believable_density_below_floor")
    generic_match = (
        silhouette.corpus_id is not None
        and silhouette.similarity >= silhouette_threshold
    )
    if generic_match:
        failures.append(f"generic_silhouette:{silhouette.corpus_id}")
    if reduced_motion.spatial_motion_count > 0:
        failures.append("reduced_motion_spatial_motion_present")
    if end_similarity < end_state_similarity_floor:
        failures.append("reduced_motion_end_state_changed")

    return VisualQualityAssessment(
        density_score=density,
        density_floor=density_floor,
        occupied_ratio=occupied,
        visible_blocks=visible,
        interactive_blocks=interactive,
        word_count=words,
        filler_detected=filler,
        silhouette=silhouette,
        reduced_motion_spatial_count=reduced_motion.spatial_motion_count,
        end_state_similarity=end_similarity,
        failures=tuple(failures),
    )
