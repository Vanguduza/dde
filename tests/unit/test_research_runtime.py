"""EDR-0019 Epic D/E research coverage, packet completeness and delta reporting."""

from __future__ import annotations

import pytest

from engine.core.errors import DdeError
from engine.research import coverage, cursor, packets

REQUIRED = ("ARCHITECTURE", "SECURITY", "TESTING")


def _cells(*states: str) -> tuple[coverage.Cell, ...]:
    return tuple(
        coverage.Cell(unit_revision="unit@1", dimension=dimension, state=state)
        for dimension, state in zip(REQUIRED, states, strict=True)
    )


def test_the_coverage_unit_is_revision_times_dimension() -> None:
    cells = coverage.seed_cells(
        unit_revisions=("unit@1", "unit@2"), dimensions=REQUIRED
    )
    assert len(cells) == 6
    assert {cell.state for cell in cells} == {"UNSEEDED"}


def test_an_unknown_dimension_is_refused() -> None:
    with pytest.raises(DdeError):
        coverage.seed_cells(unit_revisions=("unit@1",), dimensions=("ASTROLOGY",))


def test_no_useful_evidence_is_a_real_outcome_not_a_failure() -> None:
    cells = _cells("ADMITTED", "NO_USEFUL_EVIDENCE", "ADMITTED")
    assert coverage.coverage_fraction(cells) == 1.0
    assert coverage.resumable(cells) == ()


def test_resume_is_idempotent_and_never_reruns_settled_cells() -> None:
    cells = _cells("ADMITTED", "FAILED_RETRYABLE", "QUEUED")
    resumable = coverage.resumable(cells)
    assert {cell.dimension for cell in resumable} == {"SECURITY", "TESTING"}
    assert coverage.coverage_fraction(cells) == pytest.approx(1 / 3)


def test_an_illegal_cell_transition_is_refused() -> None:
    coverage.require_legal_cell_transition("QUEUED", "FIRST_PASS")
    with pytest.raises(DdeError):
        coverage.require_legal_cell_transition("QUEUED", "ADMITTED")


def test_missing_dimensions_are_named() -> None:
    cells = _cells("ADMITTED", "QUEUED", "ADMITTED")
    assert coverage.missing_dimensions(
        cells, unit_revision="unit@1", required=REQUIRED
    ) == ("SECURITY",)


def _packet(**overrides: object) -> packets.PacketState:
    base: dict[str, object] = {
        "unit_revision": "unit@1",
        "required_dimensions": REQUIRED,
        "covered_dimensions": REQUIRED,
        "has_source_identity": True,
        "has_provenance": True,
        "has_evidence": True,
        "contradictions_resolved": True,
        "is_fresh": True,
        "is_relevant": True,
        "qualification_complete": True,
        "graph_compiled": True,
        "capsule_compiled": True,
    }
    base.update(overrides)
    return packets.PacketState(**base)  # type: ignore[arg-type]


def test_a_complete_packet_is_activation_eligible() -> None:
    assessment = packets.assess(_packet())
    assert assessment.complete is True
    assert assessment.activation_eligible is True
    assert assessment.missing == ()


def test_one_model_answering_does_not_complete_a_packet() -> None:
    assessment = packets.assess(
        _packet(
            covered_dimensions=("ARCHITECTURE",),
            has_provenance=False,
            contradictions_resolved=False,
        )
    )
    assert assessment.complete is False
    assert "dimensions:SECURITY,TESTING" in assessment.missing
    assert "provenance" in assessment.missing
    assert "contradiction_status" in assessment.missing


def test_an_uncompiled_capsule_blocks_activation_without_blocking_completeness() -> (
    None
):
    assessment = packets.assess(_packet(capsule_compiled=False))
    assert assessment.complete is True
    assert assessment.activation_eligible is False


def test_a_new_contradiction_regresses_a_packet_visibly() -> None:
    before = packets.assess(_packet())
    after = packets.assess(_packet(contradictions_resolved=False))
    assert packets.regressed(before, after) is True
    assert packets.regressed(before, before) is False


@pytest.mark.parametrize("action", sorted(packets.FORBIDDEN_RESEARCH_ACTIONS))
def test_research_can_never_steer_the_programme(action: str) -> None:
    with pytest.raises(DdeError) as excinfo:
        packets.require_advisory_only(action)
    assert excinfo.value.error_code == "POLICY_DENIED"


def test_research_may_still_prepare_knowledge() -> None:
    packets.require_advisory_only("PRECACHE_REFERENCE_SOURCE")


def _cursor(**overrides: int) -> cursor.Cursor:
    base = {
        "coverage_revision": 10,
        "packet_revision": 5,
        "admission_revision": 3,
        "graph_revision": 2,
        "last_event_sequence": 100,
    }
    base.update(overrides)
    return cursor.Cursor(**base)  # type: ignore[arg-type]


def _totals(**overrides: int) -> cursor.Counters:
    base = {
        "cells_completed": 0,
        "packets_advanced": 0,
        "packets_regressed": 0,
        "new_conflicts": 0,
        "new_admissions": 0,
        "new_rejections": 0,
        "stale_invalidations": 0,
    }
    base.update(overrides)
    return cursor.Counters(**base)  # type: ignore[arg-type]


def test_a_first_observation_reports_everything_as_new() -> None:
    delta = cursor.compute_delta(
        since=None, current=_cursor(), totals=_totals(cells_completed=10)
    )
    assert delta.changed.cells_completed == 10
    assert delta.quiet is False


def test_the_delta_is_what_moved_since_the_last_cursor() -> None:
    delta = cursor.compute_delta(
        since=_cursor(coverage_revision=10, admission_revision=3),
        current=_cursor(coverage_revision=14, admission_revision=5),
        totals=_totals(),
    )
    assert delta.changed.cells_completed == 4
    assert delta.changed.new_admissions == 2
    assert delta.quiet is False


def test_no_movement_reports_quiet_rather_than_progress() -> None:
    same = _cursor()
    delta = cursor.compute_delta(since=same, current=same, totals=_totals())
    assert delta.quiet is True
    assert delta.changed.cells_completed == 0


def test_repeated_quiet_observations_read_as_stalled_not_idle() -> None:
    same = _cursor()
    delta = cursor.compute_delta(since=same, current=same, totals=_totals())
    assert cursor.stalled(delta, consecutive_quiet_observations=1) is False
    assert cursor.stalled(delta, consecutive_quiet_observations=3) is True


def test_a_regression_surfaces_in_the_delta() -> None:
    delta = cursor.compute_delta(
        since=_cursor(),
        current=_cursor(),
        totals=_totals(packets_regressed=2),
    )
    assert delta.changed.packets_regressed == 2
    assert delta.quiet is False
