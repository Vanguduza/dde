"""Production Chapter 6.5 real-telemetry engine -- the sole writer of
`routing_decision_outcomes` rows in PostgreSQL (Chapter 2.6, 3.5, 3.8).

`record_decision_outcome()` is the real production mutation call site:
`engine.verification.runner.VerificationRunnerService.run()` calls it for
every terminal (`PASSED` or `FAILED`) `VerificationRun`, inside the same
transaction as that run's own status write and the `TaskAttempt`
finalise/fail call -- Chapter 6.5's "must never be skipped" holds by
construction, not by a best-effort side call. It resolves the real
`RouteDecision` this outcome belongs to via the already-persisted
`WorkerRun.execution_plan_id -> ExecutionPlan.route_decision_id` chain
(Chapter 7.1), then persists the verdict idempotently on
`verification_run_id` (AGENTS.md's idempotency rule, the same real
`UNIQUE` constraint plus atomic `INSERT ... ON CONFLICT DO NOTHING
RETURNING` pattern `engine.attribution` uses).

**Flagged Stage 1 divergence**, disclosed on every persisted row via
`disclosed_gaps` (`engine.telemetry.rules`/`engine.telemetry.model` module
docstrings have the full rationale): actual token/tool cost is not
recorded -- `WorkerRun.usage_record_id` references a `UsageRecord`
concept no writer in this codebase produces yet.

**Substituted, not invented**: Chapter 6.5 names "context policy version"
as a telemetry field; no such versioned "context policy" concept exists
in this codebase yet (that is Chapter 5.13/EDR-0003 promotion territory).
This module stores the real, durable `ContextPackage.package_id` the
verified attempt actually used instead -- a genuine pointer a future
policy-version concept can join through, not a fabricated version string.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.routing_decision_outcome import RoutingDecisionOutcome
from engine.contracts.task import Task
from engine.contracts.verification_run import VerificationRun
from engine.contracts.worker_run import WorkerRun
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.execution.repository import ExecutionPlanRepository
from engine.recovery.matrix import RecoveryDecision
from engine.telemetry import rules
from engine.telemetry.repository import RoutingDecisionOutcomeRepository
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")


class RoutingTelemetryService:
    """Async, PostgreSQL-backed writer for `routing_decision_outcomes`
    (Chapter 3.8). Each public method opens and commits its own unit of
    work unless one is supplied, so a caller composing a cross-module
    transaction (Chapter 3.5) can share it instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        events: EventService | None = None,
        repository: RoutingDecisionOutcomeRepository | None = None,
        execution_plans: ExecutionPlanRepository | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._events = events or EventService(engine)
        self._repository = repository or RoutingDecisionOutcomeRepository()
        self._execution_plans = execution_plans or ExecutionPlanRepository()
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

    async def record_decision_outcome(
        self,
        *,
        task: Task,
        worker_run: WorkerRun,
        verification_run: VerificationRun,
        rework_count: int,
        recovery_decision: RecoveryDecision | None,
        failure_attribution_id: UUID | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> RoutingDecisionOutcome:
        """Chapter 6.5: record the real outcome-side telemetry for the
        `RouteDecision` that produced `worker_run`, once its
        `VerificationRun` reaches a terminal status."""
        if verification_run.status not in ("PASSED", "FAILED"):
            raise DdeError(
                "POLICY_DENIED",
                "telemetry is recorded only for a terminal VerificationRun",
                details={"status": verification_run.status},
            )

        async def _op(active: PostgresUnitOfWork) -> RoutingDecisionOutcome:
            plan = await self._execution_plans.get_plan(
                active.connection, worker_run.execution_plan_id
            )
            if plan is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "WorkerRun references an unknown ExecutionPlan",
                    details={"execution_plan_id": str(worker_run.execution_plan_id)},
                )
            outcome = rules.compute_outcome(
                status=verification_run.status,  # type: ignore[arg-type]
                confidence=verification_run.confidence,
                rework_count=rework_count,
                recovery_decision=recovery_decision,
                started_at=verification_run.started_at,
                ended_at=verification_run.ended_at,
            )
            now = self._clock.now()
            candidate = RoutingDecisionOutcome(
                outcome_id=uuid7(),
                tenant_id=task.tenant_id,
                project_id=task.project_id,
                mission_id=task.mission_id,
                task_id=task.task_id,
                route_decision_id=plan.route_decision_id,
                task_attempt_id=worker_run.task_attempt_id,
                verification_run_id=verification_run.verification_run_id,
                actual_verified_outcome=outcome.actual_verified_outcome,
                verification_confidence=outcome.verification_confidence,
                rework_count=outcome.rework_count,
                escalated=outcome.escalated,
                human_intervention_required=outcome.human_intervention_required,
                recovery_action=outcome.recovery_action,
                failure_class=outcome.failure_class,
                elapsed_seconds=outcome.elapsed_seconds,
                context_package_id=worker_run.context_package_id,
                capability_set=list(plan.capability_requirements),
                failure_attribution_id=failure_attribution_id,
                disclosed_gaps=list(outcome.disclosed_gaps),
                created_at=now,
                updated_at=now,
            )
            record, was_new = await self._repository.insert_or_get(
                active.connection, candidate
            )
            if was_new:
                await self._events.append(
                    tenant_id=task.tenant_id,
                    project_id=task.project_id,
                    event_type="RoutingDecisionOutcomeRecorded",
                    aggregate_type="routing_decision_outcome",
                    aggregate_id=record.outcome_id,
                    mission_id=task.mission_id,
                    task_id=task.task_id,
                    payload={
                        "route_decision_id": str(record.route_decision_id),
                        "verification_run_id": str(
                            verification_run.verification_run_id
                        ),
                        "actual_verified_outcome": record.actual_verified_outcome,
                        "rework_count": record.rework_count,
                    },
                    uow=active,
                )
            return record

        return await self._run(uow, task.tenant_id, task.project_id, _op)

    async def get_for_verification_run(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        verification_run_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> RoutingDecisionOutcome | None:
        async def _op(active: PostgresUnitOfWork) -> RoutingDecisionOutcome | None:
            return await self._repository.get_by_verification_run(
                active.connection, verification_run_id
            )

        return await self._run(uow, tenant_id, project_id, _op)
