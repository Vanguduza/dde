"""TaskAttempt — Chapter 3.3/3.8/3.9's `task_attempts` table, owned by
`engine.missions` ("TaskAttempt | missions | Attempt creator | Append-only").

No prior mission built this: `engine.missions.service.MissionService` writes
only `missions`/`tasks` (Chapter 3.8 splits `task_graphs`/`task_graph_edges`
off to `engine.planning`), and DDE-010's `engine.execution.service.
ExecutionPlanService` explicitly deferred TaskAttempt creation to "whatever
future TaskAttempt-creation caller" (its own module docstring), since Chapter
3.9 step 8 ("TaskAttempt created (worker_run_id NULL)") precedes step 9
(workspace/environment) in the chapter's literal order while DDE-010's real
implementation performs environment/workspace provisioning first. DDE-011
(this mission) is that caller: `worker_runs.task_attempt_id` is `NOT NULL`
(Chapter 8.2), so a real, persisted `WorkerRun` cannot exist without a real,
persisted `TaskAttempt` first.

This is a new, additive file — it does not modify
`engine/missions/{service,repository,tables,states}.py` at all, consistent
with the mission brief's constraint against refactoring `engine.missions`
beyond read-only calls into its *existing* public methods. `engine.workers.
service.WorkerManagerService` composes `TaskAttemptService.create()` under
its own shared transaction exactly as `engine.execution.service.
ExecutionPlanService` composes `engine.environments`/`engine.workspaces`
despite not owning those tables (Chapter 3.5: a transaction may span module
boundaries).

Deliberately minimal, per this mission's scope: only `create()` exists.
Chapter 3.9 step 15 ("TaskAttempt finalised") happens only after
verification (step 14, Chapter 11/DDE-012, out of this mission's scope), so
no status-transition surface is built here — the row is inserted once, with
`status = "IN_PROGRESS"`, and this mission never mutates it again. That
matches Chapter 3.8's "Append-only" mutability note for TaskAttempt (unlike
`ExecutionPlan`'s explicit "status mutable").
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    Column,
    Integer,
    MetaData,
    Table,
    Text,
    Uuid,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from engine.contracts.execution_plan import ExecutionPlan
from engine.contracts.task import Task
from engine.contracts.task_attempt import TaskAttempt
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

# A dedicated, independent `MetaData()` — matching every other Stage 1
# module's `tables.py` (e.g. `engine.execution.tables`), never the metadata
# object of a sibling module. `migrations/env.py` sets `target_metadata =
# None`; every module's Core `Table` here only mirrors the columns Alembic's
# hand-authored `schemas/sql/0001_stage1.sql` already created, it never
# drives autogeneration.
_metadata = MetaData()

task_attempts = Table(
    "task_attempts",
    _metadata,
    Column("attempt_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("task_id", Uuid(as_uuid=True), nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("execution_plan_id", Uuid(as_uuid=True), nullable=False),
    Column("input_context_hash", Text, nullable=False),
    Column("workspace_revision", Text, nullable=False),
    Column("result_artifact_refs", JSONB, nullable=False),
    Column("verification_refs", JSONB, nullable=False),
    Column("integration_proposal_id", Uuid(as_uuid=True), nullable=True),
    Column("status", Text, nullable=False),
    Column("failure_class", Text, nullable=True),
    Column("retry_of", Uuid(as_uuid=True), nullable=True),
    Column("checkpoint_id", Uuid(as_uuid=True), nullable=True),
    Column("started_at", TIMESTAMP(timezone=True), nullable=True),
    Column("ended_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)


class TaskAttemptRepository:
    """Reads and writes rows for `task_attempts` — the Chapter 3.8 table
    owned by `engine.missions`."""

    async def insert_attempt(
        self, connection: AsyncConnection, record: TaskAttempt
    ) -> None:
        await connection.execute(task_attempts.insert().values(**record.model_dump()))

    async def get_attempt(
        self, connection: AsyncConnection, attempt_id: UUID
    ) -> TaskAttempt | None:
        result = await connection.execute(
            select(task_attempts).where(task_attempts.c.attempt_id == attempt_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return TaskAttempt.model_validate(dict(row))

    async def next_sequence(self, connection: AsyncConnection, task_id: UUID) -> int:
        """Chapter 3.9: `task_attempts.sequence` is attempt ordinality
        within the task — "exactly one counter at each level" (3.9's
        cardinality decision), computed the same `max(sequence) + 1` way
        `engine.events.repository.EventsRepository.next_sequence` computes
        per-aggregate event ordinality."""
        result = await connection.execute(
            select(func.coalesce(func.max(task_attempts.c.sequence), 0)).where(
                task_attempts.c.task_id == task_id
            )
        )
        return int(result.scalar_one()) + 1


class TaskAttemptService:
    """Async, PostgreSQL-backed writer for `task_attempts` (Chapter 3.8).
    Each public method opens and commits its own unit of work unless one is
    supplied, so a caller composing a cross-module transaction (Chapter 3.5)
    — `engine.workers.service.WorkerManagerService` — can share it
    instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        events: EventService | None = None,
        repository: TaskAttemptRepository | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._events = events or EventService(engine)
        self._repository = repository or TaskAttemptRepository()
        self._clock = clock or SystemClock()

    async def create(
        self,
        *,
        task: Task,
        execution_plan: ExecutionPlan,
        workspace_revision: str,
        input_context_hash: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> TaskAttempt:
        """Chapter 3.9 step 8: "TaskAttempt created (worker_run_id NULL)" —
        there is no such column (3.9's own correction: the relationship is
        carried solely by `worker_runs.task_attempt_id`), so this simply
        inserts a durable, empty-result attempt row a `WorkerRun` can
        reference. `workspace_revision` is the real git revision the
        workspace was at when this attempt began (Chapter 7.5's
        `capture_revision()`/`snapshot()` output); `input_context_hash` is
        the real `ContextPackage.assembly_hash` bound to the plan — never
        fabricated."""
        if execution_plan.task_id != task.task_id:
            raise DdeError(
                "POLICY_DENIED",
                "ExecutionPlan does not belong to this task",
                details={
                    "task_id": str(task.task_id),
                    "plan_task_id": str(execution_plan.task_id),
                },
            )

        async def _op(active: PostgresUnitOfWork) -> TaskAttempt:
            sequence = await self._repository.next_sequence(
                active.connection, task.task_id
            )
            now = self._clock.now()
            attempt = TaskAttempt(
                attempt_id=uuid7(),
                tenant_id=task.tenant_id,
                project_id=task.project_id,
                mission_id=task.mission_id,
                task_id=task.task_id,
                sequence=sequence,
                execution_plan_id=execution_plan.plan_id,
                input_context_hash=input_context_hash,
                workspace_revision=workspace_revision,
                result_artifact_refs=[],
                verification_refs=[],
                integration_proposal_id=None,
                status="IN_PROGRESS",
                failure_class=None,
                retry_of=None,
                checkpoint_id=None,
                started_at=now,
                ended_at=None,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_attempt(active.connection, attempt)
            await self._events.append(
                tenant_id=task.tenant_id,
                project_id=task.project_id,
                event_type="TaskAttemptCreated",
                aggregate_type="task_attempt",
                aggregate_id=attempt.attempt_id,
                mission_id=task.mission_id,
                task_id=task.task_id,
                payload={
                    "sequence": sequence,
                    "execution_plan_id": str(execution_plan.plan_id),
                },
                uow=active,
            )
            return attempt

        if uow is not None:
            return await _op(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=task.tenant_id, project_id=task.project_id
        ) as owned:
            result = await _op(owned)
            await owned.commit()
            return result

    async def get_attempt(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        attempt_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> TaskAttempt:
        async def _op(active: PostgresUnitOfWork) -> TaskAttempt:
            record = await self._repository.get_attempt(active.connection, attempt_id)
            if record is None:
                raise DdeError("POLICY_DENIED", "Unknown task attempt")
            return record

        if uow is not None:
            return await _op(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as owned:
            result = await _op(owned)
            await owned.commit()
            return result
