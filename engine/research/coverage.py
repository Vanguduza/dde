"""Research coverage accounting.

Coverage is measurable because every cell carries an explicit state, so a mission
is never "complete" merely because a model answered. NO_USEFUL_EVIDENCE is a real
terminal outcome and is not failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from engine.core.errors import DdeError

DIMENSIONS: tuple[str, ...] = (
    "ARCHITECTURE",
    "OFFICIAL_DOCUMENTATION",
    "CURRENT_RELEASES",
    "SECURITY",
    "FAILURE_MODES",
    "TESTING",
    "PERFORMANCE",
    "DEPLOYMENT",
    "INTEGRATION",
    "UX",
    "FRONTEND_QUALITY",
    "ACCESSIBILITY",
    "SOURCE_INTELLIGENCE",
    "CONTRADICTIONS",
    "ANTI_PATTERNS",
    "WORKFLOW_AUTOMATION",
    "OBSERVABILITY",
    "COMPATIBILITY_MIGRATION",
)

#: Cell states that need no further work, whether or not evidence was found.
SETTLED_STATES = frozenset(
    {"ADMITTED", "PARTIALLY_ADMITTED", "NO_USEFUL_EVIDENCE", "FAILED_TERMINAL"}
)
#: Cell states a resume pass must pick back up.
RESUMABLE_STATES = frozenset(
    {
        "UNSEEDED",
        "QUEUED",
        "FIRST_PASS",
        "ANALYZED",
        "DEEP_EVIDENCE_PENDING",
        "DEEP_EVIDENCE_COMPLETE",
        "CONFLICTED",
        "QUALIFICATION_PENDING",
        "FAILED_RETRYABLE",
        "STALE",
    }
)

CELL_TRANSITIONS: MappingProxyType[str, frozenset[str]] = MappingProxyType(
    {
        "UNSEEDED": frozenset({"QUEUED"}),
        "QUEUED": frozenset({"FIRST_PASS", "FAILED_RETRYABLE", "FAILED_TERMINAL"}),
        "FIRST_PASS": frozenset(
            {"ANALYZED", "NO_USEFUL_EVIDENCE", "FAILED_RETRYABLE", "FAILED_TERMINAL"}
        ),
        "ANALYZED": frozenset(
            {"DEEP_EVIDENCE_PENDING", "CONFLICTED", "QUALIFICATION_PENDING"}
        ),
        "DEEP_EVIDENCE_PENDING": frozenset(
            {"DEEP_EVIDENCE_COMPLETE", "FAILED_RETRYABLE", "FAILED_TERMINAL"}
        ),
        "DEEP_EVIDENCE_COMPLETE": frozenset({"CONFLICTED", "QUALIFICATION_PENDING"}),
        "CONFLICTED": frozenset({"QUALIFICATION_PENDING", "FAILED_TERMINAL"}),
        "QUALIFICATION_PENDING": frozenset(
            {"ADMITTED", "PARTIALLY_ADMITTED", "NO_USEFUL_EVIDENCE"}
        ),
        "ADMITTED": frozenset({"STALE"}),
        "PARTIALLY_ADMITTED": frozenset({"STALE"}),
        "NO_USEFUL_EVIDENCE": frozenset({"STALE"}),
        "FAILED_RETRYABLE": frozenset({"QUEUED", "FAILED_TERMINAL"}),
        "FAILED_TERMINAL": frozenset(),
        "STALE": frozenset({"QUEUED"}),
    }
)


@dataclass(frozen=True, slots=True)
class Cell:
    unit_revision: str
    dimension: str
    state: str


def require_known_dimensions(dimensions: tuple[str, ...]) -> None:
    unknown = sorted(set(dimensions) - set(DIMENSIONS))
    if unknown:
        raise DdeError(
            "VALIDATION_FAILED",
            f"unknown research dimensions: {', '.join(unknown)}",
            retryable=False,
        )


def seed_cells(
    *, unit_revisions: tuple[str, ...], dimensions: tuple[str, ...]
) -> tuple[Cell, ...]:
    """The coverage unit is DevelopmentUnitRevision x ResearchDimension."""
    require_known_dimensions(dimensions)
    return tuple(
        Cell(unit_revision=revision, dimension=dimension, state="UNSEEDED")
        for revision in unit_revisions
        for dimension in dimensions
    )


def require_legal_cell_transition(from_state: str, to_state: str) -> None:
    allowed = CELL_TRANSITIONS.get(from_state)
    if allowed is None or to_state not in allowed:
        raise DdeError(
            "POLICY_DENIED",
            f"illegal research cell transition {from_state} -> {to_state}",
            retryable=False,
        )


def settled(cells: tuple[Cell, ...]) -> tuple[Cell, ...]:
    return tuple(cell for cell in cells if cell.state in SETTLED_STATES)


def resumable(cells: tuple[Cell, ...]) -> tuple[Cell, ...]:
    """Restart is idempotent: settled cells are never re-run."""
    return tuple(cell for cell in cells if cell.state in RESUMABLE_STATES)


def coverage_fraction(cells: tuple[Cell, ...]) -> float:
    if not cells:
        return 0.0
    return len(settled(cells)) / len(cells)


def missing_dimensions(
    cells: tuple[Cell, ...], *, unit_revision: str, required: tuple[str, ...]
) -> tuple[str, ...]:
    covered = {
        cell.dimension
        for cell in cells
        if cell.unit_revision == unit_revision and cell.state in SETTLED_STATES
    }
    return tuple(dimension for dimension in required if dimension not in covered)
