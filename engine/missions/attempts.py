"""TaskAttempt — Chapter 3.3/3.8/3.9/12.2's `task_attempts` table, owned by
`engine.missions` ("TaskAttempt | missions | Attempt creator | Append-only").

Chapter 12.2: an attempt becomes durable when its result, artifact
references and state are committed. Chapter 3.8's "Append-only" means a
retry is a new row (`retry_of`), not that the current row is frozen at
IN_PROGRESS forever. `commit_results` writes artifact refs + checkpoint_id
without finalising; `finalize` is Chapter 3.9 step 15 (after verification);
`fail` records a durable FAILED result when the worker run fails.

`create()` refuses a second attempt while a COMPLETED attempt exists for
the same task -- completed sibling work is never re-run because a later
task failed (Chapter 12.2).
"""

from __future__ import annotations

import json
from typing import Any
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
from engine.core.state_machine import transition
from engine.events.service import EventService
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

ATTEMPT_TRANSITIONS: dict[str, frozenset[str]] = {
    "IN_PROGRESS": frozenset({"COMPLETED", "FAILED"}),
    "COMPLETED": frozenset(),
    "FAILED": frozenset(),
}

ATTEMPT_COMPLETED = "ATTEMPT_COMPLETED"

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

    async def list_for_task(
        self, connection: AsyncConnection, task_id: UUID
    ) -> list[TaskAttempt]:
        result = await connection.execute(
            select(task_attempts)
            .where(task_attempts.c.task_id == task_id)
            .order_by(task_attempts.c.sequence.asc())
        )
        return [
            TaskAttempt.model_validate(dict(row)) for row in result.mappings().all()
        ]

    async def list_for_mission(
        self, connection: AsyncConnection, mission_id: UUID
    ) -> list[TaskAttempt]:
        result = await connection.execute(
            select(task_attempts)
            .where(task_attempts.c.mission_id == mission_id)
            .order_by(task_attempts.c.created_at.asc())
        )
        return [
            TaskAttempt.model_validate(dict(row)) for row in result.mappings().all()
        ]

    async def update_fields(
        self,
        connection: AsyncConnection,
        attempt_id: UUID,
        *,
        fields: dict[str, Any],
    ) -> int:
        payload = dict(fields)
        for key in ("result_artifact_refs", "verification_refs"):
            if key in payload and isinstance(payload[key], list):
                payload[key] = json.loads(json.dumps(payload[key], default=str))
        result = await connection.execute(
            task_attempts.update()
            .where(task_attempts.c.attempt_id == attempt_id)
            .values(**payload)
        )
        return int(result.rowcount)

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
        retry_of: UUID | None = None,
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
            existing = await self._repository.list_for_task(
                active.connection, task.task_id
            )
            completed = [row for row in existing if row.status == "COMPLETED"]
            if completed:
                lead = completed[0]
                raise DdeError(
                    ATTEMPT_COMPLETED,
                    "Refusing to re-run a completed TaskAttempt "
                    f"(attempt_id={lead.attempt_id})",
                    retryable=False,
                    details={
                        "task_id": str(task.task_id),
                        "attempt_id": str(lead.attempt_id),
                    },
                )
            if retry_of is not None:
                prior = next(
                    (row for row in existing if row.attempt_id == retry_of), None
                )
                if prior is None or prior.status != "FAILED":
                    raise DdeError(
                        "POLICY_DENIED",
                        "retry_of must reference a FAILED attempt of this task",
                        details={"retry_of": str(retry_of)},
                    )
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
                retry_of=retry_of,
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

    async def list_for_task(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        task_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[TaskAttempt]:
        async def _op(active: PostgresUnitOfWork) -> list[TaskAttempt]:
            return await self._repository.list_for_task(active.connection, task_id)

        if uow is not None:
            return await _op(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as owned:
            result = await _op(owned)
            await owned.commit()
            return result

    async def list_for_mission(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[TaskAttempt]:
        async def _op(active: PostgresUnitOfWork) -> list[TaskAttempt]:
            return await self._repository.list_for_mission(
                active.connection, mission_id
            )

        if uow is not None:
            return await _op(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as owned:
            result = await _op(owned)
            await owned.commit()
            return result

    async def commit_results(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        attempt_id: UUID,
        result_artifact_refs: list[UUID],
        checkpoint_id: UUID | None,
        uow: PostgresUnitOfWork | None = None,
    ) -> TaskAttempt:
        """Chapter 12.2 durability of results without Chapter 3.9 step 15
        finalisation -- verification has not run yet."""

        async def _op(active: PostgresUnitOfWork) -> TaskAttempt:
            current = await self._require(active, attempt_id)
            if current.status != "IN_PROGRESS":
                raise DdeError(
                    "VERSION_CONFLICT",
                    f"commit_results requires IN_PROGRESS (got {current.status})",
                    details={"attempt_id": str(attempt_id), "status": current.status},
                )
            now = self._clock.now()
            fields: dict[str, Any] = {
                "result_artifact_refs": result_artifact_refs,
                "checkpoint_id": checkpoint_id,
                "updated_at": now,
            }
            rowcount = await self._repository.update_fields(
                active.connection, attempt_id, fields=fields
            )
            if rowcount != 1:
                raise DdeError("POLICY_DENIED", "Unknown task attempt")
            updated = await self._require(active, attempt_id)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="TaskAttemptResultsCommitted",
                aggregate_type="task_attempt",
                aggregate_id=attempt_id,
                mission_id=updated.mission_id,
                task_id=updated.task_id,
                payload={
                    "checkpoint_id": str(checkpoint_id) if checkpoint_id else None
                },
                uow=active,
            )
            return updated

        if uow is not None:
            return await _op(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as owned:
            result = await _op(owned)
            await owned.commit()
            return result

    async def finalize(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        attempt_id: UUID,
        verification_refs: list[UUID],
        checkpoint_id: UUID | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> TaskAttempt:
        """Chapter 3.9 step 15 / 12.2: attempt becomes COMPLETED after
        verification PASSED. Production call site:
        `VerificationRunnerService.run`.
        """

        async def _op(active: PostgresUnitOfWork) -> TaskAttempt:
            current = await self._require(active, attempt_id)
            next_status = transition(current.status, "COMPLETED", ATTEMPT_TRANSITIONS)
            now = self._clock.now()
            fields: dict[str, Any] = {
                "status": next_status,
                "verification_refs": verification_refs,
                "ended_at": now,
                "updated_at": now,
            }
            if checkpoint_id is not None:
                fields["checkpoint_id"] = checkpoint_id
            rowcount = await self._repository.update_fields(
                active.connection, attempt_id, fields=fields
            )
            if rowcount != 1:
                raise DdeError("POLICY_DENIED", "Unknown task attempt")
            updated = await self._require(active, attempt_id)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="TaskAttemptFinalised",
                aggregate_type="task_attempt",
                aggregate_id=attempt_id,
                mission_id=updated.mission_id,
                task_id=updated.task_id,
                payload={
                    "verification_refs": [str(item) for item in verification_refs]
                },
                uow=active,
            )
            return updated

        if uow is not None:
            return await _op(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as owned:
            result = await _op(owned)
            await owned.commit()
            return result

    async def fail(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        attempt_id: UUID,
        failure_class: str,
        checkpoint_id: UUID | None,
        uow: PostgresUnitOfWork | None = None,
    ) -> TaskAttempt:
        """Durable FAILED result when the worker run fails or verification
        fails. A later invoke_run may create a new attempt with retry_of
        only when Chapter 12.3 permits it; this row is not replayed as success.
        """

        async def _op(active: PostgresUnitOfWork) -> TaskAttempt:
            current = await self._require(active, attempt_id)
            next_status = transition(current.status, "FAILED", ATTEMPT_TRANSITIONS)
            now = self._clock.now()
            fields: dict[str, Any] = {
                "status": next_status,
                "failure_class": failure_class,
                "checkpoint_id": checkpoint_id,
                "ended_at": now,
                "updated_at": now,
            }
            rowcount = await self._repository.update_fields(
                active.connection, attempt_id, fields=fields
            )
            if rowcount != 1:
                raise DdeError("POLICY_DENIED", "Unknown task attempt")
            updated = await self._require(active, attempt_id)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="TaskAttemptFailed",
                aggregate_type="task_attempt",
                aggregate_id=attempt_id,
                mission_id=updated.mission_id,
                task_id=updated.task_id,
                payload={"failure_class": failure_class},
                uow=active,
            )
            return updated

        if uow is not None:
            return await _op(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as owned:
            result = await _op(owned)
            await owned.commit()
            return result

    async def _require(
        self, active: PostgresUnitOfWork, attempt_id: UUID
    ) -> TaskAttempt:
        record = await self._repository.get_attempt(active.connection, attempt_id)
        if record is None:
            raise DdeError(
                "POLICY_DENIED",
                "Unknown task attempt",
                details={"attempt_id": str(attempt_id)},
            )
        return record
