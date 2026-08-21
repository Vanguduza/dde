"""Chapter 5.9 Context Critic -- triggered, not default."""

from __future__ import annotations

from datetime import UTC, datetime

from engine.context.critic import (
    DEFAULT_CRITIC_CONFIDENCE_THRESHOLD,
    evaluate_trigger,
    run_critic,
)
from engine.context.model import (
    AssembledContext,
    ContextItem,
    CoverageReport,
    FusedItem,
)
from engine.contracts.task import Task
from engine.core.ids import uuid7


def _now() -> datetime:
    return datetime.now(UTC)


def _task(**overrides: object) -> Task:
    now = _now()
    defaults: dict[str, object] = dict(
        task_id=uuid7(),
        tenant_id=uuid7(),
        project_id=uuid7(),
        mission_id=uuid7(),
        graph_id=uuid7(),
        title="t",
        intent="i",
        task_class="implementation",
        requirement_refs=["REQ-1"],
        feature_refs=[],
        success_criteria=["some criterion"],
        expected_write_scope=["pkg"],
        expected_read_scope=[],
        blast_radius="local",
        risk_class="low",
        estimated_effort="s",
        autonomy_ceiling=2,
        requires_approval=False,
        status="CREATED",
        lock_version=1,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return Task.model_validate(defaults)


def _coverage(**overrides: str) -> CoverageReport:
    defaults: dict[str, str] = dict(
        authoritative_requirements="satisfied",
        applicable_domain_rules="satisfied",
        impacted_code_and_deps="satisfied",
        architecture_constraints="satisfied",
        security_constraints="satisfied",
        verification_obligations="satisfied",
    )
    defaults.update(overrides)
    return CoverageReport(
        known_unresolved_questions=(),
        **defaults,  # type: ignore[arg-type]
    )


def _item(*, key: str, categories: tuple[str, ...], relevance: float) -> ContextItem:
    return ContextItem(
        retriever="lexical",
        key=key,
        categories=categories,
        authority_rank=8,
        rank_in_retriever=1,
        relevance=relevance,
        write_scope_match=False,
        content="x" * 40,
        source_path="pkg/mod.py",
    )


def _fused(item: ContextItem) -> FusedItem:
    return FusedItem(item=item, fused_score=1.0, contributing_retrievers=("lexical",))


def test_no_trigger_when_all_conditions_are_below_threshold() -> None:
    task = _task(risk_class="low", blast_radius="local")
    coverage = _coverage()
    included = (
        _fused(_item(key="a", categories=("impacted_code_and_deps",), relevance=1.0)),
    )
    assembled = AssembledContext(included=included, evicted=(), total_tokens=10)

    result = evaluate_trigger(task=task, coverage=coverage, assembled=assembled)

    assert result.triggered is False
    assert result.reasons == ()


def test_triggers_on_high_risk_class() -> None:
    task = _task(risk_class="high")
    coverage = _coverage()
    included = (
        _fused(_item(key="a", categories=("impacted_code_and_deps",), relevance=1.0)),
    )
    assembled = AssembledContext(included=included, evicted=(), total_tokens=10)

    result = evaluate_trigger(task=task, coverage=coverage, assembled=assembled)

    assert result.triggered is True
    assert "risk_class_high_or_above" in result.reasons


def test_triggers_on_cross_module_blast_radius() -> None:
    task = _task(blast_radius="cross_module")
    coverage = _coverage()
    included = (
        _fused(_item(key="a", categories=("impacted_code_and_deps",), relevance=1.0)),
    )
    assembled = AssembledContext(included=included, evicted=(), total_tokens=10)

    result = evaluate_trigger(task=task, coverage=coverage, assembled=assembled)

    assert "blast_radius_cross_module_or_above" in result.reasons


def test_triggers_on_partial_required_coverage_category() -> None:
    task = _task()
    coverage = _coverage(security_constraints="partial")
    included = (
        _fused(_item(key="a", categories=("impacted_code_and_deps",), relevance=1.0)),
    )
    assembled = AssembledContext(included=included, evicted=(), total_tokens=10)

    result = evaluate_trigger(task=task, coverage=coverage, assembled=assembled)

    assert "coverage_partial:security_constraints" in result.reasons


def test_repair_of_context_attributed_failure_requires_explicit_signal() -> None:
    """Chapter 5.11 (context-attributed failure) has no real data source
    in this codebase yet; `compile()` must never fabricate `True` here."""
    task = _task(task_class="repair")
    coverage = _coverage()
    included = (
        _fused(_item(key="a", categories=("impacted_code_and_deps",), relevance=1.0)),
    )
    assembled = AssembledContext(included=included, evicted=(), total_tokens=10)

    default_result = evaluate_trigger(task=task, coverage=coverage, assembled=assembled)
    assert "repair_of_context_attributed_failure" not in default_result.reasons

    explicit_result = evaluate_trigger(
        task=task,
        coverage=coverage,
        assembled=assembled,
        previously_context_attributed_failure=True,
    )
    assert "repair_of_context_attributed_failure" in explicit_result.reasons


def test_triggers_on_low_confidence() -> None:
    task = _task()
    coverage = _coverage()
    included = (
        _fused(_item(key="a", categories=("impacted_code_and_deps",), relevance=0.1)),
    )
    assembled = AssembledContext(included=included, evicted=(), total_tokens=10)

    result = evaluate_trigger(task=task, coverage=coverage, assembled=assembled)

    assert result.confidence < DEFAULT_CRITIC_CONFIDENCE_THRESHOLD
    assert any(
        reason.startswith("confidence_below_threshold") for reason in result.reasons
    )


def test_run_critic_recovers_evicted_evidence_within_budget() -> None:
    coverage = _coverage(security_constraints="partial")
    included_item = _fused(
        _item(key="a", categories=("impacted_code_and_deps",), relevance=1.0)
    )
    evicted_item = _fused(
        _item(key="b", categories=("security_constraints",), relevance=1.0)
    )
    assembled = AssembledContext(
        included=(included_item,), evicted=(evicted_item,), total_tokens=10
    )

    outcome = run_critic(coverage=coverage, assembled=assembled, budget_tokens=8000)

    assert outcome.action == "requested_additional_retrieval"
    assert outcome.reassembled is not None
    assert evicted_item in outcome.reassembled.included
    assert evicted_item not in outcome.reassembled.evicted
    assert outcome.cost_tokens_estimate > 0


def test_run_critic_raises_finding_when_no_evicted_evidence_covers_the_gap() -> None:
    coverage = _coverage(security_constraints="partial")
    included_item = _fused(
        _item(key="a", categories=("impacted_code_and_deps",), relevance=1.0)
    )
    assembled = AssembledContext(included=(included_item,), evicted=(), total_tokens=10)

    outcome = run_critic(coverage=coverage, assembled=assembled, budget_tokens=8000)

    assert outcome.action == "raised_finding"
    assert outcome.reassembled is None


def test_run_critic_raises_finding_when_recovery_would_exceed_budget() -> None:
    coverage = _coverage(security_constraints="partial")
    included_item = _fused(
        _item(key="a", categories=("impacted_code_and_deps",), relevance=1.0)
    )
    evicted_item = _fused(
        _item(key="b", categories=("security_constraints",), relevance=1.0)
    )
    assembled = AssembledContext(
        included=(included_item,), evicted=(evicted_item,), total_tokens=7999
    )

    outcome = run_critic(coverage=coverage, assembled=assembled, budget_tokens=8000)

    assert outcome.action == "raised_finding"
    assert outcome.reassembled is None
