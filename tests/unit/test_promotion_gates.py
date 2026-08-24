"""Chapter 5.13 promotion gates (`engine.context.promotion`).

`corpus_adequacy` is tested as a pure function against the Chapter 5.13
point 4 minimum-viable-corpus thresholds. `PromotionGateService.evaluate`
is tested against a real (small) corpus built the same way
`tests/unit/test_eval_corpus.py` does -- a real completed mission, not a
hand-inserted row -- to prove the `INSUFFICIENT_CORPUS` precondition is a
real, enforced gate and that idempotent re-submission observes the same
run instead of recomputing it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from engine.context.eval_corpus import EvalCorpusService
from engine.context.promotion import (
    MIN_ADVERSARIAL_CASES,
    MIN_CORPUS_SIZE,
    MIN_TASK_CLASSES,
    PromotionGateService,
    _critical_coverage_regression,
    corpus_adequacy,
)
from engine.context.service import ContextService
from engine.contracts.eval_case import EvalCase
from engine.core.ids import uuid7
from engine.overhead.formula import mean, token_cost_regressed
from tests.support.db import new_engine
from tests.support.mission_trace_fixtures import build_traceable_mission


def _case(
    *, task_class: str = "verification", is_adversarial: bool = False
) -> EvalCase:
    now = datetime.now(UTC)
    return EvalCase(
        eval_case_id=uuid7(),
        tenant_id=uuid7(),
        project_id=uuid7(),
        source_mission_id=uuid7(),
        source_task_id=uuid7(),
        source_proposal_id=uuid7(),
        task_class=task_class,
        is_adversarial=is_adversarial,
        required_refs=["a.py"],
        status="frozen",
        frozen_version=1,
        retired_reason=None,
        created_at=now,
        updated_at=now,
    )


def test_corpus_adequacy_flags_small_corpus() -> None:
    adequacy = corpus_adequacy([_case()])
    assert not adequacy.adequate
    assert adequacy.corpus_size == 1
    assert len(adequacy.reasons) == 3  # too few cases, classes, adversarial


def test_corpus_adequacy_holds_at_minimum_thresholds() -> None:
    cases = []
    for i in range(MIN_CORPUS_SIZE):
        task_class = f"class-{i % MIN_TASK_CLASSES}"
        is_adversarial = i < MIN_ADVERSARIAL_CASES
        cases.append(_case(task_class=task_class, is_adversarial=is_adversarial))
    adequacy = corpus_adequacy(cases)
    assert adequacy.adequate
    assert adequacy.corpus_size == MIN_CORPUS_SIZE
    assert adequacy.task_class_count == MIN_TASK_CLASSES
    assert adequacy.adversarial_count == MIN_ADVERSARIAL_CASES


_SATISFIED = {
    "authoritative_requirements": "satisfied",
    "applicable_domain_rules": "satisfied",
    "impacted_code_and_deps": "satisfied",
    "architecture_constraints": "satisfied",
    "security_constraints": "satisfied",
    "verification_obligations": "satisfied",
}


def test_critical_coverage_regression_none_when_candidate_holds_or_improves() -> None:
    case = _case()
    assert _critical_coverage_regression(case, _SATISFIED, dict(_SATISFIED)) is None
    improved = dict(_SATISFIED, verification_obligations="satisfied")
    baseline = dict(_SATISFIED, verification_obligations="partial")
    assert _critical_coverage_regression(case, baseline, improved) is None


def test_critical_coverage_regression_flags_worsened_category() -> None:
    case = _case()
    baseline = dict(_SATISFIED)
    candidate = dict(_SATISFIED, security_constraints="missing")
    regression = _critical_coverage_regression(case, baseline, candidate)
    assert regression is not None
    assert regression["worsened_categories"] == ["security_constraints"]


def test_critical_coverage_regression_flags_budget_exceeded() -> None:
    case = _case()
    regression = _critical_coverage_regression(case, _SATISFIED, None)
    assert regression is not None
    assert regression["reason"] == "context_budget_exceeded"
    assert regression["candidate_compiled"] is False


def test_token_cost_regressed_blocks_when_candidate_mean_rises() -> None:
    """Chapter 16.4: compile-token-cost regression blocks promotion."""
    assert token_cost_regressed(mean([10, 20]), mean([15, 25])) is True
    assert token_cost_regressed(mean([10, 20]), mean([10, 20])) is False
    assert token_cost_regressed(None, 5.0) is False


@pytest.mark.asyncio
async def test_evaluate_returns_insufficient_corpus_below_threshold(
    tmp_path: Path,
) -> None:
    """Chapter 5.13 point 4 is a real, enforced precondition: a corpus of
    one frozen case (far below 60/6/10) must never reach a PASS-shaped
    decision."""
    engine = new_engine()
    try:
        trace = await build_traceable_mission(
            engine, tmp_path, mission_slug="MISSION-PROMOTION-SMALL"
        )
        corpus_service = EvalCorpusService(engine)
        case = await corpus_service.build_case_from_integration(
            tenant_id=trace.tenant.tenant_id,
            project_id=trace.tenant.project_id,
            source_proposal_id=trace.proposal.proposal_id,
            source_mission_id=trace.mission_id,
            source_task_id=trace.advanced.task.task_id,
            task_class=trace.advanced.task.task_class,
            task_requirement_refs=trace.advanced.task.requirement_refs,
        )
        await corpus_service.freeze_case(
            tenant_id=trace.tenant.tenant_id,
            project_id=trace.tenant.project_id,
            eval_case_id=case.eval_case_id,
        )

        gate_service = PromotionGateService(engine)
        baseline = ContextService(engine, root=tmp_path)
        candidate = ContextService(
            engine, root=tmp_path, semantic_retrieval_enabled=True
        )

        run = await gate_service.evaluate(
            tenant_id=trace.tenant.tenant_id,
            project_id=trace.tenant.project_id,
            candidate_label="semantic_retrieval_enabled",
            idempotency_key="MISSION-PROMOTION-SMALL-run-1",
            baseline_service=baseline,
            candidate_service=candidate,
        )

        assert run.decision == "INSUFFICIENT_CORPUS"
        assert run.status == "COMPLETED"
        assert run.corpus_size == 1
        assert "insufficient_corpus_reasons" in run.gate_results

        # Idempotent re-submission observes the same run, it does not
        # recompute (Chapter 12.5 pattern, applied to this async operation's
        # durable identity + idempotency key + observable state).
        again = await gate_service.evaluate(
            tenant_id=trace.tenant.tenant_id,
            project_id=trace.tenant.project_id,
            candidate_label="semantic_retrieval_enabled",
            idempotency_key="MISSION-PROMOTION-SMALL-run-1",
            baseline_service=baseline,
            candidate_service=candidate,
        )
        assert again.run_id == run.run_id
    finally:
        await engine.dispose()
