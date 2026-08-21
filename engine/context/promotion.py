"""Chapter 5.13 promotion gates for a candidate context policy.

Chapter 5.13 lists five gates a new context policy must clear against the
current certified baseline, "all must hold": critical coverage,
context-attributed failure rate, contradiction rate, task success on
corpus, and token cost per verified success (reported, not gating on its
own).

**What this module actually computes.** Only `critical_coverage` is
computed here, by running `ContextService.compile()` for the baseline and
the candidate policy over every frozen corpus case's real source `Task`
and comparing the Chapter 5.8 coverage contract category-by-category. The
other four gates need the Chapter 5.11 failure-attribution pipeline and
real worker-verification runs replayed against each eval case -- a
distinct mechanism this mission does not build (see EDR-0003). `decision`
is therefore intentionally never a bare `"PASS"`: it is
`INSUFFICIENT_CORPUS`, `FAIL`, or `PARTIAL_PASS_IMPLEMENTED_GATES_ONLY`,
so nothing downstream can mistake a partial result for full Chapter 5.13
promotion. No production call site flips `ContextService`'s
`semantic_retrieval_enabled` based on this decision -- that remains a
manual, code-reviewed change per EDR-0002 until every gate exists.

**Corpus adequacy (point 4).** Chapter 5.13's minimum viable corpus is 60
cases across >= 6 task classes with >= 10 adversarial cases. `evaluate`
refuses to run any gate below that threshold and records
`INSUFFICIENT_CORPUS` instead -- a real, enforced precondition, not a
placeholder.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.context.eval_repository import (
    EvalCaseRepository,
    PromotionGateRunRepository,
)
from engine.context.model import ContextBudgetExceeded
from engine.context.service import REQUIRED_COVERAGE_CATEGORIES, ContextService
from engine.contracts.context_package import ContextPackage
from engine.contracts.eval_case import EvalCase
from engine.contracts.promotion_gate_run import PromotionGateRun
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.missions.service import MissionService
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")

MIN_CORPUS_SIZE = 60
MIN_TASK_CLASSES = 6
MIN_ADVERSARIAL_CASES = 10

_STATUS_RANK = {"missing": 0, "partial": 1, "satisfied": 2}


@dataclass(frozen=True)
class CorpusAdequacy:
    """Chapter 5.13 point 4's minimum-viable-corpus check."""

    corpus_size: int
    task_class_count: int
    adversarial_count: int
    reasons: tuple[str, ...]

    @property
    def adequate(self) -> bool:
        return not self.reasons


def corpus_adequacy(cases: list[EvalCase]) -> CorpusAdequacy:
    corpus_size = len(cases)
    task_class_count = len({case.task_class for case in cases})
    adversarial_count = sum(1 for case in cases if case.is_adversarial)
    reasons: list[str] = []
    if corpus_size < MIN_CORPUS_SIZE:
        reasons.append(
            f"corpus has {corpus_size} frozen cases, Chapter 5.13 requires "
            f">= {MIN_CORPUS_SIZE}"
        )
    if task_class_count < MIN_TASK_CLASSES:
        reasons.append(
            f"corpus spans {task_class_count} task classes, Chapter 5.13 "
            f"requires >= {MIN_TASK_CLASSES}"
        )
    if adversarial_count < MIN_ADVERSARIAL_CASES:
        reasons.append(
            f"corpus has {adversarial_count} adversarial cases, Chapter "
            f"5.13 requires >= {MIN_ADVERSARIAL_CASES}"
        )
    return CorpusAdequacy(
        corpus_size=corpus_size,
        task_class_count=task_class_count,
        adversarial_count=adversarial_count,
        reasons=tuple(reasons),
    )


def _extract_coverage(
    result: ContextPackage | ContextBudgetExceeded,
) -> dict[str, str] | None:
    if isinstance(result, ContextBudgetExceeded):
        return None
    coverage = result.coverage
    return {
        category: str(coverage[category]) for category in REQUIRED_COVERAGE_CATEGORIES
    }


def _critical_coverage_regression(
    case: EvalCase,
    baseline_coverage: dict[str, str] | None,
    candidate_coverage: dict[str, str] | None,
) -> dict[str, object] | None:
    if baseline_coverage is None or candidate_coverage is None:
        return {
            "eval_case_id": str(case.eval_case_id),
            "reason": "context_budget_exceeded",
            "baseline_compiled": baseline_coverage is not None,
            "candidate_compiled": candidate_coverage is not None,
        }
    worsened = [
        category
        for category in REQUIRED_COVERAGE_CATEGORIES
        if _STATUS_RANK[candidate_coverage[category]]
        < _STATUS_RANK[baseline_coverage[category]]
    ]
    if not worsened:
        return None
    return {"eval_case_id": str(case.eval_case_id), "worsened_categories": worsened}


class PromotionGateService:
    """Async, PostgreSQL-backed writer for `promotion_gate_runs` (Chapter
    3.8)."""

    def __init__(
        self,
        engine: AsyncEngine,
        cases: EvalCaseRepository | None = None,
        runs: PromotionGateRunRepository | None = None,
        missions: MissionService | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._cases = cases or EvalCaseRepository()
        self._runs = runs or PromotionGateRunRepository()
        self._missions = missions or MissionService(engine, EventService(engine))
        self._clock = clock or SystemClock()

    async def _run(
        self,
        uow: PostgresUnitOfWork | None,
        tenant_id: UUID,
        project_id: UUID,
        body: Callable[[PostgresUnitOfWork], Awaitable[T]],
    ) -> T:
        if uow is not None:
            return await body(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as owned:
            result = await body(owned)
            await owned.commit()
            return result

    async def evaluate(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_label: str,
        idempotency_key: str,
        baseline_service: ContextService,
        candidate_service: ContextService,
        uow: PostgresUnitOfWork | None = None,
    ) -> PromotionGateRun:
        async def _op(active: PostgresUnitOfWork) -> PromotionGateRun:
            existing = await self._runs.get_by_idempotency_key(
                active.connection, tenant_id, idempotency_key
            )
            if existing is not None:
                # Idempotency (Chapter 12.5 pattern applied here): the same
                # evaluation request observes the prior run rather than
                # recomputing and possibly diverging on a re-submit.
                return existing

            cases = await self._cases.list_frozen_corpus(
                active.connection, tenant_id, project_id
            )
            adequacy = corpus_adequacy(cases)
            now = self._clock.now()
            run_id = uuid7()

            if not adequacy.adequate:
                run = PromotionGateRun(
                    run_id=run_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    idempotency_key=idempotency_key,
                    candidate_label=candidate_label,
                    status="COMPLETED",
                    corpus_size=adequacy.corpus_size,
                    task_class_count=adequacy.task_class_count,
                    adversarial_count=adequacy.adversarial_count,
                    decision="INSUFFICIENT_CORPUS",
                    gate_results={
                        "insufficient_corpus_reasons": list(adequacy.reasons)
                    },
                    created_at=now,
                    updated_at=now,
                    completed_at=now,
                )
                await self._runs.insert_run(active.connection, run)
                return run

            regressions: list[dict[str, object]] = []
            for case in cases:
                task = await self._missions.get_task(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    task_id=case.source_task_id,
                    uow=active,
                )
                try:
                    baseline_result = await baseline_service.compile(
                        task=task, uow=active
                    )
                except DdeError as exc:
                    regressions.append(
                        {
                            "eval_case_id": str(case.eval_case_id),
                            "reason": "baseline_compile_error",
                            "error_code": exc.error_code,
                        }
                    )
                    continue
                try:
                    candidate_result = await candidate_service.compile(
                        task=task, uow=active
                    )
                except DdeError as exc:
                    regressions.append(
                        {
                            "eval_case_id": str(case.eval_case_id),
                            "reason": "candidate_compile_error",
                            "error_code": exc.error_code,
                        }
                    )
                    continue
                regression = _critical_coverage_regression(
                    case,
                    _extract_coverage(baseline_result),
                    _extract_coverage(candidate_result),
                )
                if regression is not None:
                    regressions.append(regression)

            decision = "FAIL" if regressions else "PARTIAL_PASS_IMPLEMENTED_GATES_ONLY"
            gate_results = {
                "critical_coverage": {
                    "cases_evaluated": len(cases),
                    "regressions": regressions,
                },
                "deferred_gates": [
                    "context_attributed_failure_rate",
                    "contradiction_rate",
                    "task_success_on_corpus",
                    "token_cost_per_verified_success",
                ],
            }
            run = PromotionGateRun(
                run_id=run_id,
                tenant_id=tenant_id,
                project_id=project_id,
                idempotency_key=idempotency_key,
                candidate_label=candidate_label,
                status="COMPLETED",
                corpus_size=adequacy.corpus_size,
                task_class_count=adequacy.task_class_count,
                adversarial_count=adequacy.adversarial_count,
                decision=decision,
                gate_results=gate_results,
                created_at=now,
                updated_at=now,
                completed_at=now,
            )
            await self._runs.insert_run(active.connection, run)
            return run

        return await self._run(uow, tenant_id, project_id, _op)
