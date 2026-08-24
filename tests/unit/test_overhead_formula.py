"""Pure Chapter 16.4 formula tests — failed-first arithmetic pins."""

from __future__ import annotations

from engine.overhead.formula import (
    classify_token_share,
    cost_per_verified_success,
    estimate_tokens,
    invocation_share,
    mean,
    overhead_tokens,
    percentile,
    planning_tokens_for,
    token_cost_regressed,
    token_share,
)


def test_overhead_tokens_sums_every_formula_component() -> None:
    assert (
        overhead_tokens(
            context_assembly=10,
            context_critic=3,
            routing=0,
            route_critic=0,
            planning=4,
            judge=0,
        )
        == 17
    )


def test_planning_tokens_zero_unless_model_assisted() -> None:
    texts = ("long enough rationale text", "title", "intent")
    assert planning_tokens_for(planning_mode="template", texts=texts) == 0
    assert planning_tokens_for(planning_mode="human_authored", texts=texts) == 0
    assisted = planning_tokens_for(planning_mode="model_assisted", texts=texts)
    assert assisted == estimate_tokens("\n".join(texts))
    assert assisted > 0


def test_token_share_none_when_denominator_empty() -> None:
    assert token_share(10, 0) is None
    assert token_share(10, 40) == 0.25


def test_classify_token_share_thresholds() -> None:
    assert classify_token_share(0.20) is None
    assert classify_token_share(0.26) == "alert"
    assert classify_token_share(0.36) == "investigate"
    assert classify_token_share(0.41) == "hard_cap"


def test_percentile_and_invocation_share() -> None:
    assert percentile([], 0.95) is None
    # Nearest-rank: index = int(p * (n - 1)); for n=4 and p=0.95 → 2 → 3.0.
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.95) == 3.0
    assert invocation_share(3, 10) == 0.3
    assert invocation_share(0, 0) is None


def test_cost_per_verified_success_and_regression() -> None:
    assert cost_per_verified_success(30, 3) == 10.0
    assert cost_per_verified_success(10, 0) is None
    assert token_cost_regressed(10.0, 11.0) is True
    assert token_cost_regressed(10.0, 10.0) is False
    assert token_cost_regressed(None, 5.0) is False
    assert mean([]) is None
    assert mean([2, 4, 6]) == 4.0
