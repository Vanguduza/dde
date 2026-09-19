"""Delta-first research reporting.

Progress is only understandable when the system can say what changed since the
last observation, so the Observatory answers from cursor revisions rather than
recomputing totals.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Cursor:
    coverage_revision: int
    packet_revision: int
    admission_revision: int
    graph_revision: int
    last_event_sequence: int


@dataclass(frozen=True, slots=True)
class Counters:
    cells_completed: int
    packets_advanced: int
    packets_regressed: int
    new_conflicts: int
    new_admissions: int
    new_rejections: int
    stale_invalidations: int


@dataclass(frozen=True, slots=True)
class Delta:
    cursor: Cursor
    changed: Counters
    quiet: bool


def _diff(current: int, previous: int) -> int:
    return max(0, current - previous)


def compute_delta(*, since: Cursor | None, current: Cursor, totals: Counters) -> Delta:
    """Counters are cumulative; the delta is what moved since `since`.

    A first observation reports everything as new, which is what an operator
    joining mid-mission needs to see.
    """
    if since is None:
        return Delta(cursor=current, changed=totals, quiet=False)
    changed = Counters(
        cells_completed=_diff(current.coverage_revision, since.coverage_revision),
        packets_advanced=_diff(current.packet_revision, since.packet_revision),
        packets_regressed=totals.packets_regressed,
        new_conflicts=totals.new_conflicts,
        new_admissions=_diff(current.admission_revision, since.admission_revision),
        new_rejections=totals.new_rejections,
        stale_invalidations=totals.stale_invalidations,
    )
    quiet = all(
        value == 0
        for value in (
            changed.cells_completed,
            changed.packets_advanced,
            changed.packets_regressed,
            changed.new_conflicts,
            changed.new_admissions,
            changed.new_rejections,
            changed.stale_invalidations,
        )
    )
    return Delta(cursor=current, changed=changed, quiet=quiet)


def stalled(delta: Delta, *, consecutive_quiet_observations: int) -> bool:
    """A pipeline that reports nothing repeatedly is stalled, not idle."""
    return delta.quiet and consecutive_quiet_observations >= 3
