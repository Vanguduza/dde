"""Async repositories for `worker_runs` and `worker_events` (Chapter 3.3,
3.8). Every read and write here executes on the connection of an
already-open unit of work (Chapter 3.5); this module never begins or ends a
transaction itself.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.worker_event import WorkerEvent
from engine.contracts.worker_run import WorkerRun
from engine.workers.tables import worker_events, worker_runs


class WorkerRunRepository:
    """Reads and writes rows for `worker_runs` — the Chapter 3.8 table
    owned by `engine.workers`."""

    async def insert_run(self, connection: AsyncConnection, record: WorkerRun) -> None:
        await connection.execute(worker_runs.insert().values(**record.model_dump()))

    async def get_run(
        self, connection: AsyncConnection, run_id: UUID
    ) -> WorkerRun | None:
        result = await connection.execute(
            select(worker_runs).where(worker_runs.c.run_id == run_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return WorkerRun.model_validate(dict(row))

    async def list_for_attempt(
        self, connection: AsyncConnection, task_attempt_id: UUID
    ) -> list[WorkerRun]:
        result = await connection.execute(
            select(worker_runs)
            .where(worker_runs.c.task_attempt_id == task_attempt_id)
            .order_by(worker_runs.c.sequence.asc())
        )
        return [WorkerRun.model_validate(dict(row)) for row in result.mappings().all()]

    async def list_for_project(
        self, connection: AsyncConnection, project_id: UUID, *, limit: int = 50
    ) -> list[WorkerRun]:
        result = await connection.execute(
            select(worker_runs)
            .where(worker_runs.c.project_id == project_id)
            .order_by(worker_runs.c.created_at.desc())
            .limit(limit)
        )
        return [WorkerRun.model_validate(dict(row)) for row in result.mappings().all()]

    async def list_for_profile(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        worker_profile_id: str,
        limit: int = 50,
    ) -> list[WorkerRun]:
        result = await connection.execute(
            select(worker_runs)
            .where(
                worker_runs.c.project_id == project_id,
                worker_runs.c.worker_profile_id == worker_profile_id,
            )
            .order_by(worker_runs.c.created_at.desc())
            .limit(limit)
        )
        return [WorkerRun.model_validate(dict(row)) for row in result.mappings().all()]

    async def list_for_mission(
        self, connection: AsyncConnection, mission_id: UUID
    ) -> list[WorkerRun]:
        result = await connection.execute(
            select(worker_runs)
            .where(worker_runs.c.mission_id == mission_id)
            .order_by(worker_runs.c.created_at.asc())
        )
        return [WorkerRun.model_validate(dict(row)) for row in result.mappings().all()]

    async def next_sequence(
        self, connection: AsyncConnection, task_attempt_id: UUID
    ) -> int:
        """Chapter 3.9's cardinality decision: `worker_runs.sequence` is run
        ordinality *within the attempt* (`TaskAttempt : WorkerRun` is 1:N;
        `attempt_number` was removed)."""
        result = await connection.execute(
            select(func.coalesce(func.max(worker_runs.c.sequence), 0)).where(
                worker_runs.c.task_attempt_id == task_attempt_id
            )
        )
        return int(result.scalar_one()) + 1

    async def update_run(
        self,
        connection: AsyncConnection,
        run_id: UUID,
        *,
        fields: dict[str, Any],
    ) -> int:
        """`WorkerRun` has no `lock_version` column (Chapter 8.2's field
        list omits one, as `ExecutionPlan`/`RouteDecision` also do) — the
        Worker Manager is the run's only writer within a single, sequential
        lifecycle drive, so a bare `WHERE run_id = ...` is the real
        concurrency contract here, matching
        `engine.execution.repository.ExecutionPlanRepository.update_status`.
        """
        result = await connection.execute(
            worker_runs.update().where(worker_runs.c.run_id == run_id).values(**fields)
        )
        return int(result.rowcount)


class WorkerEventRepository:
    """Reads and writes rows for `worker_events` — the Chapter 3.8 table
    owned by `engine.workers`. Chapter 8.3: "Consumers tolerate duplicates
    and bounded reordering via `(run_id, sequence)` plus idempotent
    handling" — `insert_event` is itself idempotent on that identity."""

    async def next_sequence(self, connection: AsyncConnection, run_id: UUID) -> int:
        result = await connection.execute(
            select(func.coalesce(func.max(worker_events.c.sequence), 0)).where(
                worker_events.c.run_id == run_id
            )
        )
        return int(result.scalar_one()) + 1

    async def insert_event(
        self, connection: AsyncConnection, record: WorkerEvent
    ) -> bool:
        """`ON CONFLICT DO NOTHING` on the same `(run_id, sequence,
        occurred_at)` unique index the partitioned table declares (Chapter
        3.7 requires a partitioned table's unique constraints to include
        the partition key) — a duplicate delivery of the same event is
        silently absorbed rather than raising, matching
        `engine.events.idempotency.CommandLedgerRepository.
        insert_if_absent`'s pattern. Returns whether this call actually
        inserted the row."""
        statement = (
            pg_insert(worker_events)
            .values(**record.model_dump())
            .on_conflict_do_nothing(
                index_elements=["run_id", "sequence", "occurred_at"]
            )
        )
        result = await connection.execute(statement)
        return result.rowcount == 1

    async def list_for_run(
        self, connection: AsyncConnection, run_id: UUID
    ) -> list[WorkerEvent]:
        result = await connection.execute(
            select(worker_events)
            .where(worker_events.c.run_id == run_id)
            .order_by(worker_events.c.sequence.asc())
        )
        return [
            WorkerEvent.model_validate(dict(row)) for row in result.mappings().all()
        ]
