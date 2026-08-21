"""Production Mission Kernel — the sole writer of `missions` and `tasks`
rows in PostgreSQL (Chapter 2.6, 3.5, 3.8, 4.8, 12.6).

Unlike the in-memory `MissionKernel` test double in `engine.missions.kernel`,
every method here requires an explicit tenant/project scope and persists
through a real optimistic-locking write path (Chapter 3.5): a stale
`lock_version` is rejected at the database — the `WHERE lock_version =
expected` clause on the `UPDATE` only ever matches the row a caller last
read — not merely re-derived from an in-process dict.

`create_task_graph` and `amend_task_graph` compose
`engine.planning.service.TaskGraphService` — the sole writer of
`task_graphs`/`task_graph_edges` (Chapter 3.8) — under one shared unit of
work, exactly as `engine.governance.records` composes
`TruthService`/`AuditService`/`EventService` (Chapter 3.5): a mission's
TaskGraph, its Task nodes and its edges commit, or roll back, atomically as
one PostgreSQL transaction, even though two modules each write their own
tables within it. `TaskGraphService` drives the real `DRAFT -> VALIDATING ->
APPROVED|REJECTED` lifecycle (Chapter 4.8) itself; this module inserts
`Task` rows and calls `create_edges`/`TaskGraphAmended` only when that
lifecycle actually lands on `APPROVED` (create) or activates the amendment
(amend) — never for a `REJECTED` graph.

Full `TaskPlanner.schedule()` productionization remains later.
`replan()` is `engine.recovery.dispatch.RecoveryService` (DDE-024).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.graph_amendment import GraphAmendment
from engine.contracts.mission import Mission
from engine.contracts.task import Task
from engine.contracts.task_graph import TaskGraph
from engine.contracts.task_graph_edge import TaskGraphEdge
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.missions.repository import MissionsRepository
from engine.missions.states import MISSION_TRANSITIONS, TASK_TRANSITIONS, transition
from engine.planning.service import TaskGraphService
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")


class MissionService:
    """Async, PostgreSQL-backed writer for the Chapter 3.3 mission-spine
    tables. Each public method opens and commits its own unit of work
    unless one is supplied, so a caller composing a cross-module
    transaction (Chapter 3.5) can share it instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        events: EventService,
        repository: MissionsRepository | None = None,
        task_graphs: TaskGraphService | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._events = events
        self._repository = repository or MissionsRepository()
        self._task_graphs = task_graphs or TaskGraphService(engine)
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

    async def create_mission(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        slug: str,
        title: str,
        intent: str,
        success_definition: str,
        scope: list[str],
        requirement_refs: list[str],
        autonomy_ceiling: int,
        uow: PostgresUnitOfWork | None = None,
    ) -> Mission:
        """Commit a new mission and append `MissionCommitted` in the same
        transaction (Chapter 3.9's creation order step 1)."""

        async def _op(active: PostgresUnitOfWork) -> Mission:
            existing = await self._repository.get_mission_by_slug(
                active.connection, project_id, slug
            )
            if existing is not None:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Mission slug is immutable and already used",
                    details={"slug": slug},
                )
            now = self._clock.now()
            mission = Mission(
                mission_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                slug=slug,
                title=title,
                intent=intent,
                success_definition=success_definition,
                scope=scope,
                requirement_refs=requirement_refs,
                status="CREATED",
                autonomy_ceiling=autonomy_ceiling,
                lock_version=1,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_mission(active.connection, mission)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="MissionCommitted",
                aggregate_type="mission",
                aggregate_id=mission.mission_id,
                mission_id=mission.mission_id,
                payload={"slug": slug, "status": mission.status},
                uow=active,
            )
            return mission

        return await self._run(uow, tenant_id, project_id, _op)

    async def transition_mission(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        target_status: str,
        lock_version: int,
        uow: PostgresUnitOfWork | None = None,
    ) -> Mission:
        """Move a mission to `target_status`, checked against
        `MISSION_TRANSITIONS` (Chapter 4.8, 4.9, 12.6) and guarded by
        `lock_version` (Chapter 3.5). Emits `MissionTransitioned` in the
        same transaction as the row update — Chapter 3.8's "Event ...
        Owning aggregate transaction" rule applies here exactly as it does
        to `engine.truth`/`engine.governance`."""

        async def _op(active: PostgresUnitOfWork) -> Mission:
            current = await self._require_mission(active, mission_id)
            if current.lock_version != lock_version:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Mission lock_version mismatch",
                    retryable=True,
                    details={"expected": lock_version, "actual": current.lock_version},
                )
            next_status = transition(current.status, target_status, MISSION_TRANSITIONS)
            now = self._clock.now()
            rowcount = await self._repository.update_mission_status(
                active.connection,
                mission_id,
                status=next_status,
                expected_lock_version=lock_version,
                updated_at=now,
            )
            if rowcount != 1:
                # Another writer committed between our read and our write —
                # the definitive concurrency check happens here, not above.
                refreshed = await self._require_mission(active, mission_id)
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Mission lock_version mismatch",
                    retryable=True,
                    details={
                        "expected": lock_version,
                        "actual": refreshed.lock_version,
                    },
                )
            updated = await self._require_mission(active, mission_id)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="MissionTransitioned",
                aggregate_type="mission",
                aggregate_id=mission_id,
                mission_id=mission_id,
                payload={"from": current.status, "to": updated.status},
                uow=active,
            )
            return updated

        return await self._run(uow, tenant_id, project_id, _op)

    async def get_mission(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> Mission:
        async def _op(active: PostgresUnitOfWork) -> Mission:
            return await self._require_mission(active, mission_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def get_task(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        task_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> Task:
        async def _op(active: PostgresUnitOfWork) -> Task:
            return await self._require_task(active, task_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def create_task_graph(
        self,
        *,
        mission: Mission,
        graph_id: UUID,
        tasks: list[Task],
        edges: list[TaskGraphEdge],
        planning_mode: Literal["template", "model_assisted", "human_authored"],
        planner_policy_version: str,
        rationale: str,
        created_by_principal: UUID,
        approved_requirement_slugs: set[str],
        version: int = 1,
        supersedes_id: UUID | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> TaskGraph:
        """Persist a TaskGraph with its Task nodes and edges in one
        transaction (Chapter 3.9 steps 2-3): the `task_graphs` row and its
        `task_graph_edges` are `engine.planning.TaskGraphService`'s to
        write, `tasks` rows are this module's own — composed under one
        shared unit of work so the whole thing commits, or rolls back,
        together. `TaskGraphService.create_task_graph` drives the graph
        through the real `DRAFT -> VALIDATING -> APPROVED|REJECTED`
        lifecycle (Chapter 4.8) before this method decides whether to
        materialise any `Task`/`TaskGraphEdge` rows at all: a `REJECTED`
        graph is returned as-is, durable and queryable, with no tasks or
        edges ever inserted."""

        async def _op(active: PostgresUnitOfWork) -> TaskGraph:
            graph = await self._task_graphs.create_task_graph(
                tenant_id=mission.tenant_id,
                project_id=mission.project_id,
                mission_id=mission.mission_id,
                graph_id=graph_id,
                tasks=tasks,
                edges=edges,
                planning_mode=planning_mode,
                planner_policy_version=planner_policy_version,
                rationale=rationale,
                created_by_principal=created_by_principal,
                approved_requirement_slugs=approved_requirement_slugs,
                version=version,
                supersedes_id=supersedes_id,
                uow=active,
            )
            if graph.status != "APPROVED":
                return graph
            for task in tasks:
                await self._repository.insert_task(active.connection, task)
            # Edges reference `tasks.task_id`; the Task rows above must be
            # durable in this same transaction before this FK-checked insert.
            await self._task_graphs.create_edges(
                tenant_id=mission.tenant_id,
                project_id=mission.project_id,
                edges=edges,
                uow=active,
            )
            return graph

        return await self._run(uow, mission.tenant_id, mission.project_id, _op)

    async def amend_task_graph(
        self,
        *,
        mission: Mission,
        amendment: GraphAmendment,
        new_graph_id: UUID,
        new_tasks: list[Task],
        new_edges: list[TaskGraphEdge],
        planner_policy_version: str,
        created_by_principal: UUID,
        approved_requirement_slugs: set[str],
        approval_scope_hash: str | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> TaskGraph:
        """Chapter 4.5 graph amendment, composed the same way as
        `create_task_graph`: `TaskGraphService.amend_task_graph` owns every
        `task_graphs`-row transition (the new version's validation
        lifecycle, the prior version's supersession, the new version's
        activation); this module inserts the amendment's new `Task` rows,
        persists its new `TaskGraphEdge` rows, and appends the
        `TaskGraphAmended` event — only once the amendment is actually
        accepted (`status == "ACTIVE"`), all in the same transaction."""

        async def _op(active: PostgresUnitOfWork) -> TaskGraph:
            existing_tasks = await self._repository.list_tasks_for_graph(
                active.connection, amendment.graph_id
            )
            existing_edges = await self._task_graphs.list_edges_for_graph(
                tenant_id=mission.tenant_id,
                project_id=mission.project_id,
                graph_id=amendment.graph_id,
                uow=active,
            )
            new_graph = await self._task_graphs.amend_task_graph(
                tenant_id=mission.tenant_id,
                project_id=mission.project_id,
                mission_id=mission.mission_id,
                mission_scope=mission.scope,
                mission_autonomy_ceiling=mission.autonomy_ceiling,
                amendment=amendment,
                existing_tasks=existing_tasks,
                existing_edges=existing_edges,
                new_tasks=new_tasks,
                new_edges=new_edges,
                new_graph_id=new_graph_id,
                planner_policy_version=planner_policy_version,
                created_by_principal=created_by_principal,
                approved_requirement_slugs=approved_requirement_slugs,
                approval_scope_hash=approval_scope_hash,
                uow=active,
            )
            if new_graph.status != "ACTIVE":
                return new_graph
            for task in new_tasks:
                await self._repository.insert_task(active.connection, task)
            await self._task_graphs.create_edges(
                tenant_id=mission.tenant_id,
                project_id=mission.project_id,
                edges=new_edges,
                uow=active,
            )
            await self._events.append(
                tenant_id=mission.tenant_id,
                project_id=mission.project_id,
                event_type="TaskGraphAmended",
                aggregate_type="task_graph",
                aggregate_id=new_graph.graph_id,
                mission_id=mission.mission_id,
                payload={
                    "amendment_id": str(amendment.amendment_id),
                    "amendment_type": amendment.amendment_type,
                    "justification": amendment.justification,
                    "prior_graph_id": str(amendment.graph_id),
                    "new_graph_id": str(new_graph.graph_id),
                    "new_version": new_graph.version,
                    "affected_task_ids": [
                        str(task_id) for task_id in amendment.affected_task_ids
                    ],
                    "added_task_ids": [str(task.task_id) for task in new_tasks],
                    "added_edge_ids": [str(edge.edge_id) for edge in new_edges],
                },
                uow=active,
            )
            return new_graph

        return await self._run(uow, mission.tenant_id, mission.project_id, _op)

    async def transition_task(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        task_id: UUID,
        target_status: str,
        lock_version: int,
        uow: PostgresUnitOfWork | None = None,
    ) -> Task:
        """Chapter 4.8 task lifecycle, including SUPERSEDED/RETIRED from replan."""

        async def _op(active: PostgresUnitOfWork) -> Task:
            current = await self._require_task(active, task_id)
            if current.lock_version != lock_version:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Task lock_version mismatch",
                    retryable=True,
                    details={
                        "expected": lock_version,
                        "actual": current.lock_version,
                    },
                )
            next_status = transition(current.status, target_status, TASK_TRANSITIONS)
            now = self._clock.now()
            rowcount = await self._repository.update_task(
                active.connection,
                task_id,
                fields={"status": next_status, "updated_at": now},
                expected_lock_version=lock_version,
            )
            if rowcount != 1:
                refreshed = await self._require_task(active, task_id)
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Task lock_version mismatch",
                    retryable=True,
                    details={
                        "expected": lock_version,
                        "actual": refreshed.lock_version,
                    },
                )
            updated = await self._require_task(active, task_id)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="TaskTransitioned",
                aggregate_type="task",
                aggregate_id=task_id,
                mission_id=updated.mission_id,
                task_id=task_id,
                payload={"from": current.status, "to": updated.status},
                uow=active,
            )
            return updated

        return await self._run(uow, tenant_id, project_id, _op)

    async def rebind_task_graph(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        task_id: UUID,
        graph_id: UUID,
        lock_version: int,
        uow: PostgresUnitOfWork | None = None,
    ) -> Task:
        """Move a PRESERVE/QUIESCE node onto the replan's new graph version."""

        async def _op(active: PostgresUnitOfWork) -> Task:
            current = await self._require_task(active, task_id)
            if current.lock_version != lock_version:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Task lock_version mismatch",
                    retryable=True,
                    details={
                        "expected": lock_version,
                        "actual": current.lock_version,
                    },
                )
            now = self._clock.now()
            rowcount = await self._repository.update_task(
                active.connection,
                task_id,
                fields={"graph_id": graph_id, "updated_at": now},
                expected_lock_version=lock_version,
            )
            if rowcount != 1:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Task lock_version mismatch",
                    retryable=True,
                    details={"task_id": str(task_id)},
                )
            return await self._require_task(active, task_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def insert_task(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        task: Task,
        uow: PostgresUnitOfWork | None = None,
    ) -> Task:
        async def _op(active: PostgresUnitOfWork) -> Task:
            await self._repository.insert_task(active.connection, task)
            return task

        return await self._run(uow, tenant_id, project_id, _op)

    async def list_tasks_for_graph(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        graph_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[Task]:
        async def _op(active: PostgresUnitOfWork) -> list[Task]:
            return await self._repository.list_tasks_for_graph(
                active.connection, graph_id
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def _require_mission(
        self, active: PostgresUnitOfWork, mission_id: UUID
    ) -> Mission:
        record = await self._repository.get_mission(active.connection, mission_id)
        if record is None:
            raise DdeError("POLICY_DENIED", "Unknown mission")
        return record

    async def _require_task(self, active: PostgresUnitOfWork, task_id: UUID) -> Task:
        record = await self._repository.get_task(active.connection, task_id)
        if record is None:
            raise DdeError("POLICY_DENIED", "Unknown task")
        return record
