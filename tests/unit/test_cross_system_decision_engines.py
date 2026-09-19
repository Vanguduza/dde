"""EDR-0019 decision engines: readiness, postconditions, steering, attention, facts.

Each test states the law it is defending. These are the rules the contracts only
declare; here they are executable.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from engine.attention import scoring
from engine.capabilities import gates
from engine.context import epistemics
from engine.core.errors import DdeError
from engine.missions import steering
from engine.recovery import postcondition

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


# --------------------------------------------------------------- capability gates


def _observation(**overrides: object) -> gates.GateObservation:
    base: dict[str, object] = {
        "configuration_state": "COMPLETE",
        "reachability_state": "REACHABLE",
        "qualification_state": "QUALIFIED",
        "evidence_pointer": "ev://1",
        "last_probe_at": NOW - timedelta(minutes=5),
        "expires_at": NOW + timedelta(hours=1),
    }
    base.update(overrides)
    return gates.GateObservation(**base)  # type: ignore[arg-type]


def test_ready_requires_the_whole_evidence_chain() -> None:
    assert gates.compute_readiness(_observation(), now=NOW) == gates.READY


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"evidence_pointer": None}, gates.STALE_EVIDENCE),
        ({"expires_at": NOW - timedelta(minutes=1)}, gates.STALE_EVIDENCE),
        ({"last_probe_at": None}, gates.STALE_EVIDENCE),
        ({"qualification_state": "UNQUALIFIED"}, gates.REACHABLE),
        ({"reachability_state": "UNREACHABLE"}, gates.BLOCKED_EXTERNAL),
        ({"configuration_state": "ABSENT"}, gates.UNCONFIGURED),
        ({"revoked": True}, gates.REVOKED),
        ({"owner_action_required": True}, gates.BLOCKED_OWNER),
        ({"identity_matches_expected": False}, gates.DEGRADED),
    ],
)
def test_a_configured_credential_alone_is_never_ready(
    overrides: dict[str, object], expected: str
) -> None:
    assert gates.compute_readiness(_observation(**overrides), now=NOW) == expected


def test_stale_evidence_demotes_rather_than_staying_ready() -> None:
    fresh = _observation(expires_at=NOW + timedelta(minutes=1))
    assert gates.compute_readiness(fresh, now=NOW) == gates.READY
    assert (
        gates.compute_readiness(fresh, now=NOW + timedelta(minutes=2))
        == gates.STALE_EVIDENCE
    )


def test_degraded_without_a_contract_is_refused() -> None:
    with pytest.raises(DdeError):
        gates.require_degraded_contract(gates.DEGRADED, None)
    gates.require_degraded_contract(
        gates.DEGRADED,
        gates.DegradedContract(
            broken="search index",
            still_works=("reads",),
            will_not_do=("reindex",),
            restore_action="rebuild index",
        ),
    )


def test_only_ready_and_degraded_permit_execution() -> None:
    assert not gates.blocks_execution(gates.READY)
    assert not gates.blocks_execution(gates.DEGRADED)
    assert gates.blocks_execution(gates.STALE_EVIDENCE)
    assert gates.blocks_execution(gates.BLOCKED_OWNER)


# ------------------------------------------------------------- postconditions


def test_engine_success_alone_never_produces_verified() -> None:
    assert (
        postcondition.resolve_state(policy=postcondition.REQUIRED, observations=())
        == postcondition.REQUIRED_PENDING
    )


def test_high_impact_effects_require_an_independent_observation() -> None:
    assert (
        postcondition.required_policy_for("IRREVERSIBLE")
        == postcondition.REQUIRED_INDEPENDENT
    )
    adapter_only = (
        postcondition.VerificationObservation("API_READBACK", "SUCCESS", False),
    )
    assert (
        postcondition.resolve_state(
            policy=postcondition.REQUIRED_INDEPENDENT, observations=adapter_only
        )
        == postcondition.VERIFYING
    )
    independent = (
        postcondition.VerificationObservation("DATABASE_READBACK", "SUCCESS", True),
    )
    assert (
        postcondition.resolve_state(
            policy=postcondition.REQUIRED_INDEPENDENT, observations=independent
        )
        == postcondition.VERIFIED
    )


def test_a_refutation_beats_a_success() -> None:
    observations = (
        postcondition.VerificationObservation("API_READBACK", "SUCCESS", True),
        postcondition.VerificationObservation("STATE_QUERY", "REFUTED", True),
    )
    assert (
        postcondition.resolve_state(
            policy=postcondition.REQUIRED, observations=observations
        )
        == postcondition.REFUTED
    )


def test_completion_is_refused_while_a_postcondition_is_unproven() -> None:
    pending = (
        postcondition.EffectPostcondition(
            "e1", "IRREVERSIBLE", postcondition.REQUIRED_INDEPENDENT, "VERIFYING"
        ),
    )
    with pytest.raises(DdeError) as excinfo:
        postcondition.require_completable(pending)
    assert excinfo.value.error_code == "EVIDENCE_MISSING"

    proven = (
        postcondition.EffectPostcondition(
            "e1", "IRREVERSIBLE", postcondition.REQUIRED_INDEPENDENT, "VERIFIED"
        ),
        postcondition.EffectPostcondition(
            "e2", "PURE_READ", postcondition.NOT_REQUIRED, None
        ),
    )
    postcondition.require_completable(proven)


# ------------------------------------------------------------------- steering


def _steer(**overrides: object) -> steering.SteerRequest:
    base: dict[str, object] = {
        "steer_id": "s1",
        "authority_class": "OWNER_EXPLICIT",
        "read_only": False,
        "material": True,
        "write_ownership_scope": ("src/app",),
    }
    base.update(overrides)
    return steering.SteerRequest(**base)  # type: ignore[arg-type]


def test_a_read_only_question_takes_no_barrier() -> None:
    question = _steer(read_only=True, material=False)
    assert steering.needs_barrier(question) is False
    assert steering.next_state_after_acknowledge(question) == steering.EXECUTING


def test_a_material_steer_takes_a_barrier() -> None:
    assert steering.needs_barrier(_steer()) is True
    assert steering.next_state_after_acknowledge(_steer()) == steering.BARRIER_SET


def test_no_authority_may_only_ask() -> None:
    with pytest.raises(DdeError):
        steering.require_authorized(
            _steer(authority_class="NO_AUTHORITY", read_only=False)
        )
    steering.require_authorized(
        _steer(authority_class="NO_AUTHORITY", read_only=True, material=False)
    )


def test_a_barrier_blocks_new_claims_but_waits_for_active_writers() -> None:
    scope = ("src/app",)
    assert steering.blocks_new_claim(
        barrier_scope=scope, lease_kind="WORKSPACE", requested_scope=("src/app/api",)
    )
    assert not steering.blocks_new_claim(
        barrier_scope=scope, lease_kind="WORKSPACE", requested_scope=("docs",)
    )
    mid_flight = (steering.ActiveWriter("w1", ("src/app/api",), at_boundary=None),)
    assert not steering.barrier_is_satisfied(barrier_scope=scope, active=mid_flight)
    at_boundary = (
        steering.ActiveWriter(
            "w1", ("src/app/api",), at_boundary="COMMITTED_CHECKPOINT"
        ),
    )
    assert steering.barrier_is_satisfied(barrier_scope=scope, active=at_boundary)


def test_disjoint_writers_are_not_awaited() -> None:
    assert steering.barrier_is_satisfied(
        barrier_scope=("src/app",),
        active=(steering.ActiveWriter("w2", ("docs",), at_boundary=None),),
    )


def test_illegal_steer_transition_is_refused() -> None:
    steering.require_legal_transition(steering.RECEIVED, steering.ACKNOWLEDGED)
    with pytest.raises(DdeError):
        steering.require_legal_transition(steering.RECEIVED, steering.EXECUTING)


def test_an_unnamed_boundary_is_not_a_safe_boundary() -> None:
    steering.require_safe_boundary("COMMITTED_CHECKPOINT")
    with pytest.raises(DdeError):
        steering.require_safe_boundary("PROCESS_KILLED")


# ------------------------------------------------------------------ attention


def test_security_and_approval_bypass_the_budget() -> None:
    exhausted = scoring.BudgetUsage(emitted_last_hour=99, emitted_last_day=99)
    budget = scoring.AttentionBudget(max_nonurgent_per_hour=1, max_nonurgent_per_day=5)
    for attention_class in ("SECURITY", "APPROVAL", "URGENT"):
        disposition, bypassed = scoring.disposition_for(
            attention_class=attention_class,
            candidate_score=0.1,
            budget=budget,
            usage=exhausted,
            moment=NOW,
        )
        assert (disposition, bypassed) == ("PROMOTED", True)


def test_an_info_item_is_suppressed_once_the_budget_is_spent() -> None:
    disposition, bypassed = scoring.disposition_for(
        attention_class="INFO",
        candidate_score=0.9,
        budget=scoring.AttentionBudget(
            max_nonurgent_per_hour=1, max_nonurgent_per_day=5
        ),
        usage=scoring.BudgetUsage(emitted_last_hour=1, emitted_last_day=1),
        moment=NOW,
    )
    assert disposition == "SUPPRESSED_BUDGET"
    assert bypassed is False


def test_quiet_hours_suppress_non_urgent_attention_only() -> None:
    budget = scoring.AttentionBudget(
        max_nonurgent_per_hour=10, max_nonurgent_per_day=10, quiet_hours=((22, 7),)
    )
    night = datetime(2026, 9, 19, 23, 30, tzinfo=UTC)
    assert scoring.in_quiet_hours(night, budget) is True
    quiet, _ = scoring.disposition_for(
        attention_class="FOLLOW_UP",
        candidate_score=0.9,
        budget=budget,
        usage=scoring.BudgetUsage(0, 0),
        moment=night,
    )
    assert quiet == "SUPPRESSED_QUIET_HOURS"
    urgent, bypassed = scoring.disposition_for(
        attention_class="SECURITY",
        candidate_score=0.9,
        budget=budget,
        usage=scoring.BudgetUsage(0, 0),
        moment=night,
    )
    assert (urgent, bypassed) == ("PROMOTED", True)


def test_repeats_dedupe_to_one_key_and_decay_in_score() -> None:
    key = scoring.dedupe_key("provider", "anthropic", "rate_limit")
    assert key == scoring.dedupe_key("Provider", "Anthropic", "Rate Limit")
    assert scoring.repeat_penalty_for(1) == 0.0
    assert scoring.repeat_penalty_for(3) > scoring.repeat_penalty_for(2)
    assert scoring.repeat_penalty_for(99) <= 0.35


def test_a_persistent_blocker_never_scores_to_nothing() -> None:
    inputs = scoring.ScoreInputs(
        importance=0.9,
        urgency=0.9,
        actionability=0.9,
        novelty=0.0,
        confidence=0.9,
        blast_radius=0.9,
        time_sensitivity=0.9,
        owner_required=True,
        repeat_penalty=scoring.repeat_penalty_for(99),
    )
    assert scoring.score(inputs) >= 0.5


# ----------------------------------------------------------------- epistemics


def _fact(
    authority_class: str, *, minutes: int = 0, fact_id: str = "f"
) -> epistemics.Fact:
    return epistemics.Fact(
        fact_id=fact_id,
        subject="project.runtime",
        predicate="uses",
        authority_class=authority_class,
        observed_at=NOW + timedelta(minutes=minutes),
    )


def test_project_truth_outranks_qualified_knowledge_however_fresh() -> None:
    governing = epistemics.resolve(
        (
            _fact("QUALIFIED_KNOWLEDGE", minutes=60, fact_id="new"),
            _fact("PROJECT_TRUTH", minutes=0, fact_id="truth"),
        ),
        now=NOW,
    )
    assert governing is not None
    assert governing.fact_id == "truth"


def test_a_model_inference_never_displaces_truth() -> None:
    governing = epistemics.resolve(
        (
            _fact("MODEL_INFERENCE", minutes=600, fact_id="guess"),
            _fact("PROJECT_TRUTH", fact_id="truth"),
        ),
        now=NOW,
    )
    assert governing is not None
    assert governing.fact_id == "truth"


def test_verified_live_state_may_refresh_an_observation_but_not_truth() -> None:
    assert epistemics.may_supersede(
        _fact("VERIFIED_HISTORY"), _fact("VERIFIED_LIVE_STATE")
    )
    assert not epistemics.may_supersede(
        _fact("PROJECT_TRUTH"), _fact("VERIFIED_LIVE_STATE")
    )


def test_a_learned_candidate_cannot_satisfy_a_canonical_requirement() -> None:
    with pytest.raises(DdeError):
        epistemics.require_can_satisfy_canonical(_fact("LEARNED_CANDIDATE"))
    epistemics.require_can_satisfy_canonical(_fact("PROJECT_TRUTH"))


def test_inference_reaches_the_model_labelled_not_as_settled_fact() -> None:
    inference = _fact("MODEL_INFERENCE")
    assert (
        epistemics.render_for_model(inference, "the project uses X")
        == "MODEL_INFERENCE: the project uses X"
    )
    truth = _fact("PROJECT_TRUTH")
    assert epistemics.render_for_model(truth, "the project uses X") == (
        "the project uses X"
    )


def test_inference_is_never_persisted_as_fact_without_promotion() -> None:
    with pytest.raises(DdeError):
        epistemics.require_promotable(_fact("MODEL_INFERENCE"), promoted_by_ref=None)
    epistemics.require_promotable(_fact("MODEL_INFERENCE"), promoted_by_ref="owner")


def test_a_superseded_fact_stops_governing() -> None:
    superseded = epistemics.Fact(
        fact_id="old",
        subject="s",
        predicate="p",
        authority_class="PROJECT_TRUTH",
        observed_at=NOW,
        superseded_by_fact_id="new",
    )
    assert epistemics.resolve((superseded,), now=NOW) is None
