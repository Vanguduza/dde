"""DDE-069 M7 — one write path, and the rules it cannot be talked out of.

Pure tests over lock resolution, the candidate lifecycle table and the
mutation planner. The property under test throughout is that a rule holds
regardless of which affordance asked: an inspector edit, a chat
instruction and an agent packet are the same `MutationRequest` and get the
same answer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from engine.contracts.frontend_candidate import FrontendCandidate
from engine.contracts.frontend_lock import FrontendLock
from engine.core.errors import DdeError
from engine.studio.candidates.lifecycle import (
    ALLOWED,
    MUTABLE,
    TERMINAL,
    CandidateState,
    assert_transition,
    state_after_mutation,
)
from engine.studio.locks.resolution import (
    LOCK_COVERAGE,
    covers_key,
    effective_lock_hash,
    evaluate,
)
from engine.studio.mutations.planner import MutationRequest, plan
from engine.studio.pxg.service import PxgGraph
from tests.support.pxg_fixtures import node


def _lock(kind: str, scope: str, *, status: str = "ACTIVE") -> FrontendLock:
    now = datetime.now(UTC)
    return FrontendLock(
        lock_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        lock_kind=kind,
        scope_key=scope,
        status=status,
        reason="under review",
        created_by=uuid4(),
        released_by=None,
        released_at=None,
        lock_version=1,
        created_at=now,
        updated_at=now,
    )


def _candidate(
    *,
    state: CandidateState = CandidateState.READY,
    scope_keys: tuple[str, ...] = ("screens/checkout",),
    base_revision: int = 1,
) -> FrontendCandidate:
    now = datetime.now(UTC)
    return FrontendCandidate(
        candidate_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        mission_id=None,
        workspace_id=None,
        title="Direction A",
        state=state.value,
        origin="DIRECT_EDIT",
        base_pxg_revision=base_revision,
        base_contract_version=1,
        scope_keys=list(scope_keys),
        verification_run_id=None,
        provenance={},
        state_detail=None,
        superseded_by=None,
        promoted_at=None,
        lock_version=1,
        created_at=now,
        updated_at=now,
    )


def _graph() -> PxgGraph:
    return PxgGraph(
        revision=1,
        nodes=(
            node("screens/checkout", "screen"),
            node("screens/checkout#hero", "region", parent="screens/checkout"),
            node("screens/checkout-archive", "screen"),
            node("screens/other", "screen"),
        ),
        edges=(),
    )


# --- lock resolution ---------------------------------------------------


def test_a_lock_covers_its_descendants_but_not_a_similar_sibling() -> None:
    """The segment-boundary check matters: locking `screens/checkout`
    must not lock `screens/checkout-archive`."""
    assert covers_key("screens/checkout", "screens/checkout") is True
    assert covers_key("screens/checkout", "screens/checkout#hero") is True
    assert covers_key("screens/checkout", "screens/checkout/step-2") is True
    assert covers_key("screens/checkout", "screens/checkout-archive") is False
    assert covers_key("*", "anything/at/all") is True


def test_lock_kinds_refuse_only_the_operations_they_are_about() -> None:
    """Collapsing lock kinds into one boolean is what makes people
    disable locks wholesale, so a STYLE lock must not block a MOVE."""
    style = [_lock("STYLE", "screens/checkout")]
    assert (
        evaluate(style, target_key="screens/checkout", operation="RESTYLE").allowed
        is False
    )
    assert (
        evaluate(style, target_key="screens/checkout", operation="MOVE").allowed is True
    )

    structure = [_lock("STRUCTURE", "screens/checkout")]
    assert (
        evaluate(structure, target_key="screens/checkout", operation="MOVE").allowed
        is False
    )
    assert (
        evaluate(structure, target_key="screens/checkout", operation="RESTYLE").allowed
        is True
    )


def test_a_global_design_lock_refuses_every_operation() -> None:
    locks = [_lock("GLOBAL_DESIGN", "*")]
    for operation in LOCK_COVERAGE["GLOBAL_DESIGN"]:
        assert (
            evaluate(locks, target_key="screens/x", operation=operation).allowed
            is False
        )


def test_a_released_lock_does_not_block() -> None:
    locks = [_lock("STYLE", "screens/checkout", status="RELEASED")]
    assert evaluate(locks, target_key="screens/checkout", operation="RESTYLE").allowed


def test_the_blocking_reason_names_the_lock_and_its_rationale() -> None:
    decision = evaluate(
        [_lock("SECTION", "screens/checkout")],
        target_key="screens/checkout#hero",
        operation="REMOVE",
    )
    assert decision.allowed is False
    assert "SECTION" in (decision.reason or "")
    assert "under review" in (decision.reason or "")


def test_the_lock_hash_changes_with_the_active_set_only() -> None:
    active = [_lock("STYLE", "screens/a")]
    base = effective_lock_hash(active)
    assert effective_lock_hash(list(reversed(active))) == base

    with_released = [*active, _lock("SECTION", "screens/b", status="RELEASED")]
    assert effective_lock_hash(with_released) == base, (
        "releasing a lock widens what is permitted; a plan made under the "
        "stricter set stays valid"
    )

    with_active = [*active, _lock("SECTION", "screens/b")]
    assert effective_lock_hash(with_active) != base


# --- candidate lifecycle ----------------------------------------------


def test_there_is_no_transition_that_skips_the_promotion_gate() -> None:
    """PROMOTING is where the gate runs, so no state may reach PROMOTED
    without passing through it."""
    for state, targets in ALLOWED.items():
        if CandidateState.PROMOTED in targets:
            assert state is CandidateState.PROMOTING, (
                f"{state.value} can reach PROMOTED directly, bypassing the gate"
            )


def test_terminal_states_have_no_exits() -> None:
    for state in TERMINAL:
        assert ALLOWED[state] == frozenset(), state.value


def test_an_illegal_transition_is_refused_with_the_legal_set() -> None:
    with pytest.raises(DdeError) as excinfo:
        assert_transition(CandidateState.EDITING, CandidateState.PROMOTED)
    assert excinfo.value.error_code == "POLICY_DENIED"
    assert "allowed" in excinfo.value.details

    with pytest.raises(DdeError) as excinfo:
        assert_transition(CandidateState.READY, CandidateState.READY)
    assert excinfo.value.error_code == "VALIDATION_FAILED"


def test_editing_a_verified_candidate_drops_its_verdict() -> None:
    """The evidence described the code before the edit. Keeping the badge
    is how an unverified change reaches promotion."""
    assert state_after_mutation(CandidateState.VERIFIED) is CandidateState.DIRTY
    assert state_after_mutation(CandidateState.PROMOTABLE) is CandidateState.DIRTY


def test_a_promoted_candidate_is_not_mutable() -> None:
    assert CandidateState.PROMOTED not in MUTABLE
    assert CandidateState.REJECTED not in MUTABLE
    assert CandidateState.VERIFYING not in MUTABLE


# --- mutation planning -------------------------------------------------


def _request(**kwargs: object) -> MutationRequest:
    base: dict[str, object] = {
        "operation": "SET_PROPERTY",
        "target_key": "screens/checkout#hero",
        "origin": "INSPECTOR",
        "payload": {"property": "spacing", "value": "space4"},
    }
    base.update(kwargs)
    return MutationRequest(**base)  # type: ignore[arg-type]


def test_the_same_edit_gets_the_same_answer_from_every_affordance() -> None:
    """A rule enforced in one entry point and forgotten in another is not
    a rule."""
    locks = [_lock("STYLE", "screens/checkout")]
    for origin in (
        "INSPECTOR",
        "CHAT",
        "DIRECT_MANIPULATION",
        "AGENT",
        "DESIGN_PROVIDER",
    ):
        result = plan(
            [_request(origin=origin)],
            candidate=_candidate(),
            graph=_graph(),
            locks=locks,
        )
        assert result.planned == ()
        assert result.refused[0].code == "LOCK_DENIED", origin


def test_an_edit_outside_the_candidate_scope_is_refused() -> None:
    result = plan(
        [_request(target_key="screens/other")],
        candidate=_candidate(scope_keys=("screens/checkout",)),
        graph=_graph(),
        locks=[],
    )
    assert result.refused[0].code == "SCOPE_DENIED"


def test_a_candidate_is_stale_when_the_accepted_base_has_advanced() -> None:
    result = plan(
        [_request()],
        candidate=_candidate(base_revision=1),
        graph=_graph(),
        locks=[],
        accepted_pxg_revision=2,
    )
    assert result.planned == ()
    assert result.refused[0].code == "STALE_CANDIDATE"
    assert "revision 1 to 2" in result.refused[0].detail


def test_token_discipline_survives_the_new_write_path() -> None:
    """DDE-067 refuses freehand literals at the canvas boundary. The V2
    inspector must not become a hole in the same rule."""
    refused = plan(
        [_request(payload={"property": "color", "value": "#1177bb"})],
        candidate=_candidate(),
        graph=_graph(),
        locks=[],
    )
    assert refused.refused[0].code == "OFF_TOKEN_REFUSED"

    accepted = plan(
        [_request(payload={"property": "color", "value": "--accent-primary"})],
        candidate=_candidate(),
        graph=_graph(),
        locks=[],
    )
    assert accepted.planned and not accepted.refused


def test_a_non_style_property_is_not_forced_through_the_token_catalogue() -> None:
    result = plan(
        [_request(payload={"property": "aria_label", "value": "Continue"})],
        candidate=_candidate(),
        graph=_graph(),
        locks=[],
    )
    assert result.planned and not result.refused


def test_an_immutable_candidate_refuses_every_request() -> None:
    for state in (
        CandidateState.PROMOTED,
        CandidateState.VERIFYING,
        CandidateState.REJECTED,
        CandidateState.GENERATING,
    ):
        result = plan(
            [_request()],
            candidate=_candidate(state=state),
            graph=_graph(),
            locks=[],
        )
        assert result.refused[0].code == "MUTATION_INVALID", state.value


def test_editing_a_node_that_does_not_exist_is_refused() -> None:
    result = plan(
        [_request(target_key="screens/checkout#ghost")],
        candidate=_candidate(scope_keys=("screens/checkout",)),
        graph=_graph(),
        locks=[],
    )
    assert result.refused[0].code == "MUTATION_INVALID"
    assert "no PXG node" in result.refused[0].detail


def test_add_does_not_require_the_node_to_exist_yet() -> None:
    result = plan(
        [
            _request(
                operation="ADD",
                target_key="screens/checkout#new",
                payload={"node_kind": "component", "title": "New"},
            )
        ],
        candidate=_candidate(scope_keys=("screens/checkout",)),
        graph=_graph(),
        locks=[],
    )
    assert result.planned and not result.refused


def test_the_whole_batch_is_planned_so_every_problem_surfaces_at_once() -> None:
    result = plan(
        [
            _request(),
            _request(target_key="screens/other"),
            _request(payload={"property": "color", "value": "#abcdef"}),
        ],
        candidate=_candidate(),
        graph=_graph(),
        locks=[],
    )
    assert len(result.planned) == 1
    assert {item.code for item in result.refused} == {
        "SCOPE_DENIED",
        "OFF_TOKEN_REFUSED",
    }
    assert result.is_applicable is False


def test_the_inverse_is_captured_from_state_before_the_edit() -> None:
    """After application the prior value is gone, so an inverse computed
    later would be a guess."""
    graph = PxgGraph(
        revision=1,
        nodes=(
            node("screens/checkout", "screen"),
            node(
                "screens/checkout#hero",
                "region",
                parent="screens/checkout",
                attributes={"spacing": "space2"},
            ),
        ),
        edges=(),
    )
    result = plan([_request()], candidate=_candidate(), graph=graph, locks=[])
    inverse = result.planned[0].inverse
    assert inverse["property"] == "spacing"
    assert inverse["value"] == "space2"


def test_preconditions_record_the_state_the_plan_was_made_against() -> None:
    locks = [_lock("SECTION", "screens/other")]
    result = plan(
        [_request()],
        candidate=_candidate(base_revision=1),
        graph=_graph(),
        locks=locks,
        contract_version=3,
        design_system_hash="abc123",
    )
    pre = result.planned[0].preconditions
    assert pre.pxg_revision == 1
    assert pre.candidate_base_revision == 1
    assert pre.frontend_contract_version == 3
    assert pre.design_system_hash == "abc123"
    assert pre.effective_lock_hash == effective_lock_hash(locks)


def test_unknown_operations_and_origins_are_refused() -> None:
    for kwargs in ({"operation": "OBLITERATE"}, {"origin": "SOMEWHERE"}):
        result = plan(
            [_request(**kwargs)],
            candidate=_candidate(),
            graph=_graph(),
            locks=[],
        )
        assert result.refused[0].code == "MUTATION_INVALID"
