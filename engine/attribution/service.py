"""Production Chapter 5.11 failure-attribution engine -- the sole writer
of `failure_attributions` rows in PostgreSQL (Chapter 2.6, 3.5, 3.8).

`attribute_verification_failure()` is the real production mutation call
site: `engine.verification.runner.VerificationRunnerService.run()` calls
it, inside the same transaction as the `FAILED` `VerificationRun` update
and the `TaskAttempt.fail()` call, whenever a verification run's outcome
is `FAILED`. It composes two already-persisted, real production signals
-- the task's most recent `ContextPackage.coverage` (Chapter 5.8) and the
real git diff of the failed run's `Workspace` against its `base_revision`
(Chapter 7.5) -- into `engine.attribution.rules.attribute_failure`'s
deterministic verdict, then persists it idempotently on
`verification_run_id` (Chapter 5.11's failure-attribution record is
naturally one-per-run; AGENTS.md's idempotency rule is enforced by a real
`UNIQUE` constraint plus an atomic `INSERT ... ON CONFLICT DO NOTHING
RETURNING`, not a separate check-then-insert).

**Flagged Stage 1 divergences**, both disclosed on every persisted row via
`rule_reasons` (`engine.attribution.rules` module docstring has the full
rationale), not silently dropped:

1. Chapter 5.11's third deterministic check ("did the worker request
   context that existed but was not supplied?") needs Chapter 5.12's
   just-in-time expansion, which no writer in this codebase produces yet.
2. Chapter 5.11's model-judgment fallback for rule-inconclusive cases is
   not implemented -- the same no-model-call constraint
   `engine.context.critic`/`engine.context.conflict` hold to. An
   inconclusive rule outcome is persisted honestly as `inconclusive`.

**Chapter 6.8 consumer.** The routing-learning exclusion filter is
consumed by `engine.learning.service.ExperienceRecordService.
record_from_verification()`, called from
`VerificationRunnerService.run()`'s terminal branches. Simulation-origin
rows are written by `RoutingSimulationService.run_regression()` and
remain ineligible by construction.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.attribution import rules
from engine.attribution.repository import FailureAttributionRepository
from engine.context.repository import ContextRepository
from engine.contracts.failure_attribution import FailureAttribution
from engine.contracts.task import Task
from engine.contracts.workspace import Workspace
from engine.core.clock import Clock, SystemClock
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work
from engine.workspaces import git

T = TypeVar("T")


class FailureAttributionService:
    """Async, PostgreSQL-backed writer for `failure_attributions`
    (Chapter 3.8). Each public method opens and commits its own unit of
    work unless one is supplied, so a caller composing a cross-module
    transaction (Chapter 3.5) can share it instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        events: EventService | None = None,
        repository: FailureAttributionRepository | None = None,
        context_repository: ContextRepository | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._events = events or EventService(engine)
        self._repository = repository or FailureAttributionRepository()
        self._context_repository = context_repository or ContextRepository()
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

    async def attribute_verification_failure(
        self,
        *,
        task: Task,
        task_attempt_id: UUID,
        verification_run_id: UUID,
        workspace: Workspace,
        uow: PostgresUnitOfWork | None = None,
    ) -> FailureAttribution:
        """Chapter 5.11: run the deterministic rule set against this
        task's real, most recently compiled `ContextPackage.coverage` and
        the real changed-paths diff of `workspace` since its
        `base_revision`, then persist the verdict."""

        async def _op(active: PostgresUnitOfWork) -> FailureAttribution:
            versions = await self._context_repository.list_versions_for_task(
                active.connection, task.task_id
            )
            coverage = versions[-1].coverage if versions else None
            changed_paths = self._changed_paths(workspace)
            result = rules.attribute_failure(
                coverage=coverage,
                expected_write_scope=task.expected_write_scope,
                changed_paths=changed_paths,
            )
            now = self._clock.now()
            candidate = FailureAttribution(
                attribution_id=uuid7(),
                tenant_id=task.tenant_id,
                project_id=task.project_id,
                mission_id=task.mission_id,
                task_id=task.task_id,
                task_attempt_id=task_attempt_id,
                verification_run_id=verification_run_id,
                outcome=result.outcome,
                category=result.category,
                method=result.method,
                rule_reasons=list(result.rule_reasons),
                confidence=result.confidence,
                eligible_for_promotion_gating=result.eligible_for_promotion_gating,
                excluded_from_routing_learning=result.excluded_from_routing_learning,
                created_at=now,
                updated_at=now,
            )
            attribution, was_new = await self._repository.insert_or_get(
                active.connection, candidate
            )
            if was_new:
                await self._events.append(
                    tenant_id=task.tenant_id,
                    project_id=task.project_id,
                    event_type="FailureAttributionRecorded",
                    aggregate_type="failure_attribution",
                    aggregate_id=attribution.attribution_id,
                    mission_id=task.mission_id,
                    task_id=task.task_id,
                    payload={
                        "verification_run_id": str(verification_run_id),
                        "outcome": attribution.outcome,
                        "category": attribution.category,
                        "rule_reasons": attribution.rule_reasons,
                    },
                    uow=active,
                )
            return attribution

        return await self._run(uow, task.tenant_id, task.project_id, _op)

    def _changed_paths(self, workspace: Workspace) -> list[str]:
        if workspace.workspace_path is None or workspace.base_revision is None:
            return []
        try:
            return git.diff_name_only(
                Path(workspace.workspace_path), workspace.base_revision
            )
        except git.GitCommandError:
            # A worktree that has already been cleaned up, or a base
            # revision that no longer resolves, is real absence of
            # evidence, not a fabricated "no overreach" answer -- reported
            # as no changed paths rather than raised, since a failed
            # verification must still get a durable attribution row.
            return []

    async def get_for_verification_run(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        verification_run_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> FailureAttribution | None:
        async def _op(active: PostgresUnitOfWork) -> FailureAttribution | None:
            return await self._repository.get_by_verification_run(
                active.connection, verification_run_id
            )

        return await self._run(uow, tenant_id, project_id, _op)
