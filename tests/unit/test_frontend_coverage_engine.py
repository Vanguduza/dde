"""DDE-069 — the Coverage Engine must not launder uncertainty.

Pure tests over `engine.studio.coverage.scoring` and `.thinness`. The
behaviour under test is the distinction the golden coverage ring depends
on: *missing* is a failure, *unverified* is unknown, *blocked* and
*waived* are decisions, and a percentage exists only when nothing is
unknown.
"""

from __future__ import annotations

from uuid import uuid4

from engine.contracts.frontend_contract import Obligation
from engine.contracts.pxg_node import PxgNode
from engine.studio.coverage.scoring import (
    CoverageState,
    ObligationOutcome,
    evaluate_obligation,
    findings_for,
    summarise,
    summarise_dimension,
)
from engine.studio.coverage.thinness import detect
from engine.studio.pxg.service import PxgGraph
from tests.support.pxg_fixtures import node


def _obligation(
    *,
    key: str,
    dimension: str = "screen",
    applicability: str = "REQUIRED",
    decision_ref: str | None = None,
    verification_kinds: tuple[str, ...] = (),
) -> Obligation:
    return Obligation(
        obligation_id=uuid4(),
        dimension=dimension,
        pxg_key=key,
        statement=f"{key} must exist",
        requirement_refs=[],
        applicability=applicability,
        applicability_decision_ref=decision_ref,
        verification_kinds=list(verification_kinds),
    )


def test_missing_and_unverified_are_different_outcomes() -> None:
    """The distinction the whole engine exists for: a screen nobody built
    and a screen nobody checked are not the same fact."""
    built = frozenset({"screens/a"})

    absent = evaluate_obligation(
        _obligation(key="screens/b"),
        implemented_keys=built,
        passing_verifications={},
    )
    assert absent.outcome is ObligationOutcome.MISSING

    unchecked = evaluate_obligation(
        _obligation(key="screens/a", verification_kinds=("visual_critique",)),
        implemented_keys=built,
        passing_verifications={},
    )
    assert unchecked.outcome is ObligationOutcome.UNVERIFIED
    assert "visual_critique" in unchecked.detail

    checked = evaluate_obligation(
        _obligation(key="screens/a", verification_kinds=("visual_critique",)),
        implemented_keys=built,
        passing_verifications={"screens/a": frozenset({"visual_critique"})},
    )
    assert checked.outcome is ObligationOutcome.SATISFIED


def test_partially_passing_verification_is_still_unverified() -> None:
    result = evaluate_obligation(
        _obligation(
            key="screens/a",
            verification_kinds=("visual_critique", "silhouette"),
        ),
        implemented_keys=frozenset({"screens/a"}),
        passing_verifications={"screens/a": frozenset({"silhouette"})},
    )
    assert result.outcome is ObligationOutcome.UNVERIFIED
    assert "visual_critique" in result.detail
    assert "silhouette" not in result.detail


def test_waivers_leave_the_denominator_and_blocks_do_not() -> None:
    """A waived obligation is not a gap. A blocked one is still counted,
    because blocked work is outstanding work."""
    evaluations = [
        evaluate_obligation(
            _obligation(key="screens/a"),
            implemented_keys=frozenset({"screens/a"}),
            passing_verifications={},
        ),
        evaluate_obligation(
            _obligation(
                key="screens/b",
                applicability="NOT_APPLICABLE_APPROVED",
                decision_ref="EDR-9999",
            ),
            implemented_keys=frozenset(),
            passing_verifications={},
        ),
        evaluate_obligation(
            _obligation(
                key="screens/c",
                applicability="BLOCKED_RECORDED",
                decision_ref="RISK-01",
            ),
            implemented_keys=frozenset(),
            passing_verifications={},
        ),
    ]
    result = summarise_dimension("screen", evaluations)
    assert result.waived_count == 1
    assert result.blocked_count == 1
    assert result.required_count == 2, "the waiver left the denominator"
    assert result.state == CoverageState.PARTIAL.value
    assert result.percent is None


def test_a_dimension_with_nothing_unknown_gets_a_percentage() -> None:
    evaluations = [
        evaluate_obligation(
            _obligation(key=f"screens/{name}"),
            implemented_keys=frozenset({"screens/a", "screens/b", "screens/c"}),
            passing_verifications={},
        )
        for name in ("a", "b", "c", "d")
    ]
    result = summarise_dimension("screen", evaluations)
    assert result.state == CoverageState.ASSESSED.value
    assert result.satisfied_count == 3
    assert result.missing_count == 1
    assert result.percent == 75.0


def test_summary_withholds_a_number_unless_every_dimension_is_assessed() -> None:
    assessed = summarise_dimension(
        "screen",
        [
            evaluate_obligation(
                _obligation(key="screens/a"),
                implemented_keys=frozenset({"screens/a"}),
                passing_verifications={},
            )
        ],
    )
    partial = summarise_dimension(
        "accessibility",
        [
            evaluate_obligation(
                _obligation(
                    key="screens/a",
                    dimension="accessibility",
                    verification_kinds=("visual_critique",),
                ),
                implemented_keys=frozenset({"screens/a"}),
                passing_verifications={},
            )
        ],
    )

    state, percent = summarise([assessed])
    assert (state, percent) == (CoverageState.ASSESSED, 100.0)

    state, percent = summarise([assessed, partial])
    assert state is CoverageState.PARTIAL
    assert percent is None, "one unknown dimension must suppress the number"


def test_a_fully_blocked_project_is_blocked_not_zero_percent() -> None:
    blocked = summarise_dimension(
        "screen",
        [
            evaluate_obligation(
                _obligation(
                    key="screens/a",
                    applicability="BLOCKED_RECORDED",
                    decision_ref="RISK-01",
                ),
                implemented_keys=frozenset(),
                passing_verifications={},
            )
        ],
    )
    state, percent = summarise([blocked])
    assert state is CoverageState.BLOCKED
    assert percent is None


def test_an_empty_contract_dimension_set_is_unassessed_not_complete() -> None:
    state, percent = summarise([])
    assert state is CoverageState.UNASSESSED
    assert percent is None


def test_weighting_is_by_obligation_count_not_by_dimension() -> None:
    """A dimension holding one obligation must not outvote one holding
    many; otherwise a tiny perfect dimension inflates the ring."""
    big = summarise_dimension(
        "screen",
        [
            evaluate_obligation(
                _obligation(key=f"screens/{index}"),
                implemented_keys=frozenset(),
                passing_verifications={},
            )
            for index in range(9)
        ],
    )
    small = summarise_dimension(
        "journey",
        [
            evaluate_obligation(
                _obligation(key="journeys/a", dimension="journey"),
                implemented_keys=frozenset({"journeys/a"}),
                passing_verifications={},
            )
        ],
    )
    state, percent = summarise([big, small])
    assert state is CoverageState.ASSESSED
    assert percent == 10.0


def test_every_non_satisfied_outcome_becomes_a_drilldown_finding() -> None:
    evaluations = [
        evaluate_obligation(
            _obligation(key="screens/a"),
            implemented_keys=frozenset({"screens/a"}),
            passing_verifications={},
        ),
        evaluate_obligation(
            _obligation(key="screens/b"),
            implemented_keys=frozenset(),
            passing_verifications={},
        ),
    ]
    findings = findings_for(evaluations)
    assert len(findings) == 1
    assert findings[0].finding_kind == "MISSING"
    assert findings[0].pxg_key == "screens/b"


def _graph(*nodes: PxgNode) -> PxgGraph:
    return PxgGraph(revision=1, nodes=tuple(nodes), edges=())


def test_thinness_flags_a_data_screen_with_no_empty_or_error_state() -> None:
    graph = _graph(
        node("screens/orders", "screen", title="Orders"),
        node("screens/orders#table", "region", parent="screens/orders"),
        node(
            "screens/orders#rows",
            "data_binding",
            parent="screens/orders#table",
        ),
        node(
            "screens/orders#loading",
            "state",
            parent="screens/orders#table",
            attributes={"state_name": "loading"},
        ),
    )
    findings = detect(graph)
    thin = [item for item in findings if item.dimension == "data_state"]
    assert len(thin) == 1
    assert "empty" in thin[0].detail and "error" in thin[0].detail
    assert "loading" not in thin[0].detail


def test_thinness_flags_an_interaction_that_does_nothing() -> None:
    graph = _graph(
        node("screens/a", "screen"),
        node("screens/a#save", "interaction", parent="screens/a"),
    )
    findings = detect(graph)
    assert any(
        item.pxg_key == "screens/a#save" and "command_ref" in item.detail
        for item in findings
    )


def test_thinness_flags_a_destructive_action_without_confirmation() -> None:
    graph = _graph(
        node("screens/a", "screen"),
        node(
            "screens/a#delete",
            "interaction",
            parent="screens/a",
            attributes={"command_ref": "orders.delete", "destructive": True},
        ),
    )
    findings = detect(graph)
    assert any("confirmation" in item.detail for item in findings)


def test_a_complete_screen_produces_no_thinness_findings() -> None:
    graph = _graph(
        node("screens/a", "screen"),
        node("screens/a#table", "region", parent="screens/a"),
        node("screens/a#rows", "data_binding", parent="screens/a#table"),
        node(
            "screens/a#loading",
            "state",
            parent="screens/a#table",
            attributes={"state_name": "loading"},
        ),
        node(
            "screens/a#empty",
            "state",
            parent="screens/a#table",
            attributes={"state_name": "empty"},
        ),
        node(
            "screens/a#error",
            "state",
            parent="screens/a#table",
            attributes={"state_name": "error"},
        ),
        node(
            "screens/a#delete",
            "interaction",
            parent="screens/a",
            attributes={
                "command_ref": "orders.delete",
                "destructive": True,
                "confirmation_ref": "dialogs/confirm-delete",
            },
        ),
    )
    assert detect(graph) == ()


def test_a_screen_with_no_children_is_flagged_as_a_shell() -> None:
    graph = _graph(node("screens/empty", "screen"))
    findings = detect(graph)
    assert any("no regions or components" in item.detail for item in findings)
