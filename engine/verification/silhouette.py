"""Silhouette-distinctiveness gate for rendered screens (DDE-068, playbook
§10.3: "Playwright screenshot -> coarse layout-shape fingerprint (block
positions, column count, hero grammar) compared against a corpus of
documented generic layouts; near-match = review blocker regardless of
palette.").

**Determinism (playbook §10.3 acceptance criteria):** identical PNG bytes
always produce the identical occupancy grid and the identical
`fingerprint_hash` -- this is a pure function over pixel statistics, no
model call, no randomness.

**Corpus provenance (EDR-0016 acceptance, decision 6):** the generic-layout
corpus is self-generated from the playbook's own named tells (§1 "Named
tells recur across independent catalogs" / §10.2's "Inter-only type +
indigo-family accent + centered-hero-3-card skeleton"), hand-authored as
ASCII occupancy grids below -- not scraped from any gallery
(SOURCE_REFERENCE_ONLY / no-APIs law, playbook §10.5). Provenance is
trivially internal: every template traces to a name already written in this
repository's own playbook text.

**Coarseness (§10.3 "coarse ... fingerprint"):** the render is reduced to a
`GRID_COLS` x `GRID_ROWS` boolean occupancy grid -- a cell is "content" when
its luminance variance clears `CONTENT_VARIANCE_THRESHOLD` (flat
background/whitespace has near-zero variance; text, borders, images and
cards do not). Comparison against the corpus is a Jaccard similarity over
that grid, which is invariant to the actual colors used ("near-match ...
regardless of palette").
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

from engine.core.errors import DdeError

GRID_COLS = 12
GRID_ROWS = 8
#: A cell is "content" if it has internal texture (edges/text over a flat
#: fill) ...
CONTENT_VARIANCE_THRESHOLD = 60.0
#: ... OR its mean luminance departs from the page background luminance by
#: at least this much on a 0-255 scale -- catches solid-fill content (a
#: flat-colored card or hero band has ~zero internal variance but a mean far
#: from the background).
CONTENT_MEAN_DELTA_THRESHOLD = 25.0
#: playbook §10.3: "near-match = review blocker regardless of palette."
NEAR_MATCH_THRESHOLD = 0.85


def _parse_template(rows: tuple[str, ...]) -> tuple[bool, ...]:
    occupancy: list[bool] = []
    for row in rows:
        if len(row) != GRID_COLS:
            raise ValueError(f"template row must be {GRID_COLS} chars: {row!r}")
        occupancy.extend(char == "#" for char in row)
    if len(occupancy) != GRID_COLS * GRID_ROWS:
        raise ValueError(f"template must have {GRID_ROWS} rows")
    return tuple(occupancy)


@dataclass(frozen=True)
class GenericLayoutTemplate:
    """One named, self-generated occupancy grid from the playbook's own
    catalog of recurring generic-output tells."""

    name: str
    playbook_reference: str
    occupancy: tuple[bool, ...]


#: Self-generated, license-clean corpus (EDR-0016 decision 6). Each template
#: traces to a tell already named in `docs/planning/dde-frontend-ux-playbook.md`.
GENERIC_LAYOUT_CORPUS: tuple[GenericLayoutTemplate, ...] = (
    GenericLayoutTemplate(
        name="centered-hero-3-card",
        playbook_reference="§10.2: centered-hero-3-card skeleton",
        occupancy=_parse_template(
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
        ),
    ),
    GenericLayoutTemplate(
        name="centered-hero-plus-badge",
        playbook_reference="§1: centered-hero-plus-badge skeletons",
        occupancy=_parse_template(
            (
                "....####....",
                "..########..",
                "..########..",
                "..########..",
                "............",
                "............",
                "............",
                "............",
            )
        ),
    ),
)


@dataclass(frozen=True)
class SilhouetteFingerprint:
    grid_cols: int
    grid_rows: int
    occupancy: tuple[bool, ...]
    fingerprint_hash: str


@dataclass(frozen=True)
class SilhouetteVerdict:
    fingerprint: SilhouetteFingerprint
    matched_template: str | None
    similarity: float
    blocked: bool
    detail: str


def _occupancy_hash(occupancy: tuple[bool, ...]) -> str:
    return hashlib.sha256(bytes(1 if cell else 0 for cell in occupancy)).hexdigest()


def compute_fingerprint(
    png_bytes: bytes,
    *,
    grid_cols: int = GRID_COLS,
    grid_rows: int = GRID_ROWS,
) -> SilhouetteFingerprint:
    """Reduce a rendered screenshot to a coarse content/empty occupancy grid.

    Pure and deterministic: the same PNG bytes always produce the same
    occupancy tuple and the same `fingerprint_hash`.
    """
    if not png_bytes:
        raise DdeError(
            "POLICY_DENIED",
            "silhouette fingerprint requires non-empty PNG bytes",
            details={},
        )
    try:
        from PIL import Image, ImageStat  # type: ignore[import-not-found]
    except ImportError as exc:
        raise DdeError(
            "POLICY_DENIED",
            "pillow is required for the silhouette gate; install the "
            "optional 'browser' extra (HPND, Chapter 9.6)",
            details={"dependency": "pillow"},
        ) from exc

    image = Image.open(io.BytesIO(png_bytes)).convert("L")
    width, height = image.size
    if width <= 0 or height <= 0:
        raise DdeError(
            "POLICY_DENIED",
            "silhouette fingerprint requires a non-empty image",
            details={"width": width, "height": height},
        )
    #: Background luminance: the modal (most frequent) value in the
    #: histogram -- robust because a page's background fill always covers
    #: more pixels than any individual content element.
    histogram = image.histogram()
    background_luminance = float(max(range(256), key=lambda v: histogram[v]))
    cell_w = width / grid_cols
    cell_h = height / grid_rows
    occupancy: list[bool] = []
    for row in range(grid_rows):
        y0 = int(row * cell_h)
        y1 = max(y0 + 1, int((row + 1) * cell_h)) if row < grid_rows - 1 else height
        for col in range(grid_cols):
            x0 = int(col * cell_w)
            x1 = max(x0 + 1, int((col + 1) * cell_w)) if col < grid_cols - 1 else width
            cell = image.crop((x0, y0, x1, y1))
            stat = ImageStat.Stat(cell)
            variance = stat.var[0]
            mean_delta = abs(stat.mean[0] - background_luminance)
            is_content = (
                variance >= CONTENT_VARIANCE_THRESHOLD
                or mean_delta >= CONTENT_MEAN_DELTA_THRESHOLD
            )
            occupancy.append(is_content)
    occupancy_t = tuple(occupancy)
    return SilhouetteFingerprint(
        grid_cols=grid_cols,
        grid_rows=grid_rows,
        occupancy=occupancy_t,
        fingerprint_hash=_occupancy_hash(occupancy_t),
    )


@dataclass(frozen=True)
class DensityEvidence:
    """Deterministic, measurable density facts about a rendered screen.

    DDE-068 keeps two density layers strictly apart (they must never
    impersonate each other):

    - **this** -- deterministic *evidence*: what fraction of the canvas
      carries content, how it is distributed, how much dead space runs
      unbroken. Reproducible, model-free, cheap.
    - the playbook section 8.3 *believable-density judgment* -- whether the
      sample data is realistic enough that hierarchy, rhythm and states can
      be judged at all. That is perceptual, scored 1-5 by the rubric critic
      (`engine.verification.visual_critique`), and no arithmetic here
      substitutes for it.

    These numbers are supplied to the critic as context, never as its
    verdict.
    """

    occupied_cells: int
    total_cells: int
    occupancy_ratio: float
    occupied_rows: int
    occupied_columns: int
    largest_empty_row_run: int
    top_half_ratio: float
    bottom_half_ratio: float


def compute_density_evidence(fingerprint: SilhouetteFingerprint) -> DensityEvidence:
    """Derive deterministic density evidence from an already-computed
    occupancy grid -- no second render, no model call."""
    cols = fingerprint.grid_cols
    rows = fingerprint.grid_rows
    grid = [fingerprint.occupancy[row * cols : (row + 1) * cols] for row in range(rows)]
    occupied_cells = sum(1 for cell in fingerprint.occupancy if cell)
    total_cells = cols * rows
    occupied_rows = sum(1 for row in grid if any(row))
    occupied_columns = sum(
        1 for col in range(cols) if any(grid[row][col] for row in range(rows))
    )

    largest_empty_run = 0
    current_run = 0
    for row in grid:
        if any(row):
            current_run = 0
        else:
            current_run += 1
            largest_empty_run = max(largest_empty_run, current_run)

    split = rows // 2
    top_cells = sum(1 for row in grid[:split] for cell in row if cell)
    bottom_cells = sum(1 for row in grid[split:] for cell in row if cell)
    top_total = max(1, split * cols)
    bottom_total = max(1, (rows - split) * cols)

    return DensityEvidence(
        occupied_cells=occupied_cells,
        total_cells=total_cells,
        occupancy_ratio=occupied_cells / total_cells if total_cells else 0.0,
        occupied_rows=occupied_rows,
        occupied_columns=occupied_columns,
        largest_empty_row_run=largest_empty_run,
        top_half_ratio=top_cells / top_total,
        bottom_half_ratio=bottom_cells / bottom_total,
    )


def _jaccard_similarity(a: tuple[bool, ...], b: tuple[bool, ...]) -> float:
    intersection = sum(1 for x, y in zip(a, b, strict=True) if x and y)
    union = sum(1 for x, y in zip(a, b, strict=True) if x or y)
    if union == 0:
        return 0.0
    return intersection / union


def evaluate_silhouette(
    png_bytes: bytes,
    *,
    corpus: tuple[GenericLayoutTemplate, ...] = GENERIC_LAYOUT_CORPUS,
    near_match_threshold: float = NEAR_MATCH_THRESHOLD,
) -> SilhouetteVerdict:
    """Compute the fingerprint and compare against the generic-layout
    corpus. `blocked=True` means a near-match was found -- playbook §10.3:
    "near-match = review blocker regardless of palette."
    """
    fingerprint = compute_fingerprint(png_bytes)
    best_name: str | None = None
    best_similarity = 0.0
    for template in corpus:
        similarity = _jaccard_similarity(fingerprint.occupancy, template.occupancy)
        if similarity > best_similarity:
            best_similarity = similarity
            best_name = template.name
    blocked = best_similarity >= near_match_threshold
    if blocked:
        detail = (
            f"near-match against generic-layout corpus entry {best_name!r} "
            f"(similarity={best_similarity:.3f} >= threshold={near_match_threshold})"
        )
    else:
        matched = (
            f" (closest: {best_name!r} similarity={best_similarity:.3f})"
            if best_name
            else ""
        )
        detail = f"no generic-layout near-match{matched}"
    return SilhouetteVerdict(
        fingerprint=fingerprint,
        matched_template=best_name if blocked else None,
        similarity=best_similarity,
        blocked=blocked,
        detail=detail,
    )
