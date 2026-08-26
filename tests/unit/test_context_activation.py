"""Chapter 5.13 context-policy activation gates: refuse when unmet.

Canary and promoted require a full Chapter 5.13 promotion run (empty
deferred_gates). PARTIAL_PASS never flips production compile(). Shadow
is observation-only.
"""

from __future__ import annotations

from uuid import uuid4

from engine.context.activation import (
    can_transition,
    compile_policy_from_activation,
    evaluate_activation_gates,
    last_certified_mode,
)
from engine.core.ids import uuid7


def test_can_transition_is_one_step_only() -> None:
    assert can_transition(current="certified_baseline", target="shadow")
    assert not can_transition(current="certified_baseline", target="canary")
    assert not can_transition(current="shadow", target="promoted")
    assert can_transition(current="canary", target="promoted")
    assert can_transition(current="shadow", target="shadow")


def test_rollback_returns_last_certified_never_untested() -> None:
    assert (
        last_certified_mode(current="canary", certified="certified_baseline")
        == "certified_baseline"
    )
    assert last_certified_mode(current="canary", certified=None) == "certified_baseline"
    assert last_certified_mode(current="shadow", certified="promoted") == "promoted"


def test_shadow_advance_is_allowed_without_promotion_run() -> None:
    verdict = evaluate_activation_gates(
        current_mode="certified_baseline",
        requested_mode="shadow",
        candidate_arm="push",
        promotion_decision=None,
        deferred_gates=None,
    )
    assert verdict.allowed
    assert verdict.refused_reasons == ()


def test_canary_refused_on_partial_pass() -> None:
    verdict = evaluate_activation_gates(
        current_mode="shadow",
        requested_mode="canary",
        candidate_arm="semantic",
        promotion_decision="PARTIAL_PASS_IMPLEMENTED_GATES_ONLY",
        deferred_gates=(
            "context_attributed_failure_rate",
            "task_success_on_corpus",
        ),
    )
    assert not verdict.allowed
    assert "partial_pass_does_not_flip_production" in verdict.refused_reasons
    assert any(
        reason.startswith("chapter_5_13_gates_incomplete")
        for reason in verdict.refused_reasons
    )


def test_canary_refused_on_insufficient_corpus() -> None:
    verdict = evaluate_activation_gates(
        current_mode="shadow",
        requested_mode="canary",
        candidate_arm="push",
        promotion_decision="INSUFFICIENT_CORPUS",
        deferred_gates=("context_attributed_failure_rate", "task_success_on_corpus"),
    )
    assert not verdict.allowed
    assert "insufficient_corpus" in verdict.refused_reasons


def test_canary_refused_when_skipping_from_baseline() -> None:
    verdict = evaluate_activation_gates(
        current_mode="certified_baseline",
        requested_mode="canary",
        candidate_arm="semantic",
        promotion_decision=None,
        deferred_gates=None,
    )
    assert not verdict.allowed
    assert verdict.refused_reasons == ("illegal_mode_transition",)


def test_compile_policy_shadow_serves_certified_pull() -> None:
    policy = compile_policy_from_activation(
        mode="shadow",
        candidate_arm="semantic",
        canary_fraction=1.0,
        task_id=uuid7(),
    )
    assert policy.semantic_enabled is False
    assert policy.assembly_arm == "pull"
    assert policy.source == "shadow"


def test_compile_policy_canary_slice_applies_semantic() -> None:
    task_id = uuid4()
    policy = compile_policy_from_activation(
        mode="canary",
        candidate_arm="semantic",
        canary_fraction=1.0,
        task_id=task_id,
    )
    assert policy.semantic_enabled is True
    assert policy.source == "canary"


def test_compile_policy_canary_control_stays_pull() -> None:
    policy = compile_policy_from_activation(
        mode="canary",
        candidate_arm="semantic",
        canary_fraction=0.0,
        task_id=uuid7(),
    )
    assert policy.semantic_enabled is False
    assert policy.source == "canary_control"
