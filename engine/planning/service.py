"""Production TaskGraph service — the sole writer of `task_graphs` and
`task_graph_edges` rows in PostgreSQL (Chapter 3.8, 3.9, 4.2, 4.3).

`create_task_graph` reuses `engine.planning.validate.validate_graph`, the
same deterministic, pure check `TaskPlanner.validate()` runs in-memory
(Chapter 4.2, 4.3), and runs the real `DRAFT -> VALIDATING ->
APPROVED|REJECTED` lifecycle (Chapter 4.8) as three durable status-column
writes against the same row — an insert followed by two guarded updates —
rather than landing directly on a terminal status. `validate`, like the
rest of the Task Planner contract (Chapter 4.3), is deterministic code that
applies identically regardless of `planning_mode`; the "human gate" Chapter
4.3's planning-mode table describes for `model_assisted`/`human_authored`
graphs sits between `APPROVED` and `ACTIVE` (i.e. who may call
`activate_task_graph`), not inside this validation sequence, so `template`
mode's "no human gate" requirement falls out of `create_task_graph`
completing DRAFT->VALIDATING->APPROVED|REJECTED unattended within one call,
with no extra code path needed.

An invalid graph does **not** raise: it is persisted as REJECTED (a real,
queryable terminal status) exactly like a valid graph is persisted as
APPROVED — only structurally malformed *input* (a task/edge whose
tenant/project/mission/graph scope doesn't match the graph being created)
raises before anything is written, matching how a caller-side programming
error is distinguished from a legitimate planning outcome elsewhere in this
codebase.

`Task` rows are `engine.missions`' to write (Chapter 3.8); this service
accepts `tasks` only to validate the graph and to compute its canonical
`graph_hash`. Persisting a TaskGraph's `Task` nodes and `TaskGraphEdge` rows
therefore takes two calls into this service — `create_task_graph` then
`create_edges` — with the caller (`engine.missions.service.MissionService`)
inserting `Task` rows in between, in the same shared unit of work: `tasks`'
foreign key to `task_graphs` requires the graph row first, and
`task_graph_edges`' foreign keys to `tasks` require the task rows before the
edges (Chapter 3.9 steps 2-3). This mirrors how `engine.governance.records`
composes `TruthService`/`AuditService`/`EventService` under one shared unit
of work (Chapter 3.5). `amend_task_graph` follows the identical split for
Chapter 4.5 graph amendments: it owns every `task_graphs`-table transition
(the new version's DRAFT->VALIDATING->APPROVED|REJECTED, the prior
version's ACTIVE->AMENDING->SUPERSEDED, and the new version's
APPROVED->ACTIVE activation) but never touches `Task` rows or
`task_graph_edges` — `MissionService.amend_task_graph` inserts the
amendment's new `Task` rows and calls `create_edges` afterward, then
appends the `TaskGraphAmended` event, all under the same shared transaction.

Full `TaskPlanner` productionization of `schedule()` remains a later
concern. `replan()` is productionized by `engine.recovery.dispatch.
RecoveryService` (DDE-024 / Chapter 4.6).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.graph_amendment import GraphAmendment
from engine.contracts.task import Task
from engine.contracts.task_graph import TaskGraph
from engine.contracts.task_graph_edge import TaskGraphEdge
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.missions.states import GRAPH_TRANSITIONS, transition
from engine.planning.hashing import graph_hash
from engine.planning.repository import TaskGraphRepository
from engine.planning.validate import in_scope, validate_graph
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")

# Chapter 4.5 rule 2: only these amendment types are auto-acceptable without
# a human. `widen_scope` (rule 3), `split_task` and `retire_task` all touch
# concerns this vertical slice deliberately does not build (governance
# approval, in-flight task supersession) and are refused outright below.
AUTO_ACCEPTED_AMENDMENT_TYPES = frozenset({"add_task", "add_edge"})


def _check_task_scope(
    tasks: list[Task],
    *,
    graph_id: UUID,
    mission_id: UUID,
    tenant_id: UUID,
    project_id: UUID,
) -> None:
    for task in tasks:
        if (
            task.graph_id != graph_id
            or task.mission_id != mission_id
            or task.tenant_id != tenant_id
            or task.project_id != project_id
        ):
            raise DdeError(
                "GRAPH_INVALID",
                "Task scope does not match the graph being created",
                details={"task_id": str(task.task_id)},
            )


def _check_edge_scope(
    edges: list[TaskGraphEdge],
    *,
    graph_id: UUID,
    mission_id: UUID,
    tenant_id: UUID,
    project_id: UUID,
) -> None:
    for edge in edges:
        if (
            edge.graph_id != graph_id
            or edge.mission_id != mission_id
            or edge.tenant_id != tenant_id
            or edge.project_id != project_id
        ):
            raise DdeError(
                "GRAPH_INVALID",
                "Edge scope does not match the graph being created",
                details={"edge_id": str(edge.edge_id)},
            )


class TaskGraphService:
    """Async, PostgreSQL-backed writer for the Chapter 3.8 TaskGraph-spine
    tables. Each public method opens and commits its own unit of work
    unless one is supplied, so a caller composing a cross-module
    transaction (Chapter 3.5) can share it instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: TaskGraphRepository | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or TaskGraphRepository()
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

    async def create_task_graph(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
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
        """Persist the `task_graphs` row (Chapter 3.9 step 2) through the
        real `DRAFT -> VALIDATING -> APPROVED|REJECTED` lifecycle
        (Chapter 4.8). `tasks`/`edges` are used for validation and
        `graph_hash` only — neither is written here; call `create_edges`
        afterward, once the caller has inserted the `Task` rows this
        graph's edges reference, and only if the returned graph's `status`
        is `APPROVED`."""
        _check_task_scope(
            tasks,
            graph_id=graph_id,
            mission_id=mission_id,
            tenant_id=tenant_id,
            project_id=project_id,
        )
        _check_edge_scope(
            edges,
            graph_id=graph_id,
            mission_id=mission_id,
            tenant_id=tenant_id,
            project_id=project_id,
        )

        async def _op(active: PostgresUnitOfWork) -> TaskGraph:
            return await self._persist_lifecycle(
                active,
                graph_id=graph_id,
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                version=version,
                supersedes_id=supersedes_id,
                planning_mode=planning_mode,
                planner_policy_version=planner_policy_version,
                rationale=rationale,
                created_by_principal=created_by_principal,
                tasks=tasks,
                edges=edges,
                approved_requirement_slugs=approved_requirement_slugs,
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def amend_task_graph(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        mission_scope: list[str],
        mission_autonomy_ceiling: int,
        amendment: GraphAmendment,
        existing_tasks: list[Task],
        existing_edges: list[TaskGraphEdge],
        new_tasks: list[Task],
        new_edges: list[TaskGraphEdge],
        new_graph_id: UUID,
        planner_policy_version: str,
        created_by_principal: UUID,
        approved_requirement_slugs: set[str],
        uow: PostgresUnitOfWork | None = None,
    ) -> TaskGraph:
        """Chapter 4.5 graph amendment. `add_task`/`add_edge` amendments
        within the mission's declared `scope` and at or below its
        `autonomy_ceiling` are auto-accepted (rule 2) — persisted as
        `version + 1` with `supersedes_id` pointing at the graph being
        amended (Chapter 3.8: TaskGraph "Versioned; prior versions
        immutable"). Every other amendment type — `widen_scope` above all
        (rule 3) — requires human approval that does not exist yet
        (Chapter 13/DDE-026) and is refused here rather than silently
        accepted; so is any `add_task` node whose scope or autonomy ceiling
        would itself require that approval.

        On acceptance this method also retires the amended-away version
        (`ACTIVE -> AMENDING -> SUPERSEDED`) and activates the new one
        (`APPROVED -> ACTIVE`) in the same transaction, so a mission never
        has two ACTIVE graphs at once. It never writes `Task` rows or
        `task_graph_edges` itself — the caller inserts `new_tasks` and
        calls `create_edges` for `new_edges` only if the returned graph's
        `status` is `ACTIVE`."""
        if amendment.amendment_type not in AUTO_ACCEPTED_AMENDMENT_TYPES:
            raise DdeError(
                "SCOPE_VIOLATION",
                f"Amendment type {amendment.amendment_type} requires "
                "governance approval and cannot be auto-accepted",
                details={"amendment_type": amendment.amendment_type},
            )
        for task in new_tasks:
            out_of_scope = [
                path
                for path in task.expected_write_scope
                if not in_scope(path, mission_scope)
            ]
            if out_of_scope:
                raise DdeError(
                    "SCOPE_VIOLATION",
                    "Amendment write scope exceeds the mission's declared scope",
                    details={"task_id": str(task.task_id), "paths": out_of_scope},
                )
            if task.autonomy_ceiling > mission_autonomy_ceiling:
                raise DdeError(
                    "SCOPE_VIOLATION",
                    "Amendment raises a node above the mission autonomy ceiling",
                    details={
                        "task_id": str(task.task_id),
                        "autonomy_ceiling": task.autonomy_ceiling,
                        "mission_autonomy_ceiling": mission_autonomy_ceiling,
                    },
                )
        _check_task_scope(
            new_tasks,
            graph_id=new_graph_id,
            mission_id=mission_id,
            tenant_id=tenant_id,
            project_id=project_id,
        )
        _check_edge_scope(
            new_edges,
            graph_id=new_graph_id,
            mission_id=mission_id,
            tenant_id=tenant_id,
            project_id=project_id,
        )

        async def _op(active: PostgresUnitOfWork) -> TaskGraph:
            current = await self._require_task_graph(active, amendment.graph_id)
            # Precondition only — raises without persisting anything if the
            # graph being amended isn't ACTIVE; the real AMENDING write
            # happens only once the new version is known to be APPROVED.
            transition(current.status, "AMENDING", GRAPH_TRANSITIONS)

            new_graph = await self._persist_lifecycle(
                active,
                graph_id=new_graph_id,
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                version=current.version + 1,
                supersedes_id=current.graph_id,
                planning_mode=current.planning_mode,
                planner_policy_version=planner_policy_version,
                rationale=amendment.justification,
                created_by_principal=created_by_principal,
                tasks=[*existing_tasks, *new_tasks],
                edges=[*existing_edges, *new_edges],
                approved_requirement_slugs=approved_requirement_slugs,
            )
            if new_graph.status != "APPROVED":
                return new_graph

            await self._advance_status(
                active,
                current.graph_id,
                from_status=current.status,
                to_status="AMENDING",
                lock_version=current.lock_version,
            )
            await self._advance_status(
                active,
                current.graph_id,
                from_status="AMENDING",
                to_status="SUPERSEDED",
                lock_version=current.lock_version + 1,
            )
            return await self._advance_status(
                active,
                new_graph.graph_id,
                from_status=new_graph.status,
                to_status="ACTIVE",
                lock_version=new_graph.lock_version,
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def create_edges(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        edges: list[TaskGraphEdge],
        uow: PostgresUnitOfWork | None = None,
    ) -> list[TaskGraphEdge]:
        """Persist `task_graph_edges` rows (Chapter 3.9 step 3). Callers
        must insert the `Task` rows an edge references first, in the same
        unit of work — `from_task_id`/`to_task_id` foreign-key `tasks`."""

        async def _op(active: PostgresUnitOfWork) -> list[TaskGraphEdge]:
            for edge in edges:
                await self._repository.insert_edge(active.connection, edge)
            return edges

        return await self._run(uow, tenant_id, project_id, _op)

    async def activate_task_graph(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        graph_id: UUID,
        lock_version: int,
        uow: PostgresUnitOfWork | None = None,
    ) -> TaskGraph:
        """`APPROVED -> ACTIVE` (Chapter 4.8), guarded by `lock_version`
        exactly as `MissionService.transition_mission` guards mission
        rows."""

        async def _op(active: PostgresUnitOfWork) -> TaskGraph:
            current = await self._require_task_graph(active, graph_id)
            if current.lock_version != lock_version:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "TaskGraph lock_version mismatch",
                    retryable=True,
                    details={"expected": lock_version, "actual": current.lock_version},
                )
            return await self._advance_status(
                active,
                graph_id,
                from_status=current.status,
                to_status="ACTIVE",
                lock_version=lock_version,
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def get_task_graph(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        graph_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> TaskGraph:
        async def _op(active: PostgresUnitOfWork) -> TaskGraph:
            return await self._require_task_graph(active, graph_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def list_edges_for_graph(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        graph_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[TaskGraphEdge]:
        async def _op(active: PostgresUnitOfWork) -> list[TaskGraphEdge]:
            return await self._repository.list_edges_for_graph(
                active.connection, graph_id
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def replan_task_graph(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        prior_graph_id: UUID,
        new_graph_id: UUID,
        keep_tasks: list[Task],
        new_tasks: list[Task],
        edges: list[TaskGraphEdge],
        planner_policy_version: str,
        created_by_principal: UUID,
        approved_requirement_slugs: set[str],
        rationale: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> TaskGraph:
        """Chapter 4.8: ACTIVE → REPLANNING → SUPERSEDED on the prior
        version; new version DRAFT→VALIDATING→APPROVED→ACTIVE. Does not
        write Task rows (engine.missions).
        """

        async def _op(active: PostgresUnitOfWork) -> TaskGraph:
            current = await self._require_task_graph(active, prior_graph_id)
            transition(current.status, "REPLANNING", GRAPH_TRANSITIONS)
            combined = [*keep_tasks, *new_tasks]
            _check_task_scope(
                combined,
                graph_id=new_graph_id,
                mission_id=mission_id,
                tenant_id=tenant_id,
                project_id=project_id,
            )
            _check_edge_scope(
                edges,
                graph_id=new_graph_id,
                mission_id=mission_id,
                tenant_id=tenant_id,
                project_id=project_id,
            )
            new_graph = await self._persist_lifecycle(
                active,
                graph_id=new_graph_id,
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                version=current.version + 1,
                supersedes_id=current.graph_id,
                planning_mode=current.planning_mode,
                planner_policy_version=planner_policy_version,
                rationale=rationale,
                created_by_principal=created_by_principal,
                tasks=combined,
                edges=edges,
                approved_requirement_slugs=approved_requirement_slugs,
            )
            if new_graph.status != "APPROVED":
                return new_graph
            await self._advance_status(
                active,
                current.graph_id,
                from_status=current.status,
                to_status="REPLANNING",
                lock_version=current.lock_version,
            )
            await self._advance_status(
                active,
                current.graph_id,
                from_status="REPLANNING",
                to_status="SUPERSEDED",
                lock_version=current.lock_version + 1,
            )
            return await self._advance_status(
                active,
                new_graph.graph_id,
                from_status=new_graph.status,
                to_status="ACTIVE",
                lock_version=new_graph.lock_version,
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def _persist_lifecycle(
        self,
        active: PostgresUnitOfWork,
        *,
        graph_id: UUID,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        version: int,
        supersedes_id: UUID | None,
        planning_mode: Literal["template", "model_assisted", "human_authored"],
        planner_policy_version: str,
        rationale: str,
        created_by_principal: UUID,
        tasks: list[Task],
        edges: list[TaskGraphEdge],
        approved_requirement_slugs: set[str],
    ) -> TaskGraph:
        """Insert a graph as `DRAFT`, then drive it through `VALIDATING` to
        `APPROVED`/`REJECTED` (Chapter 4.8) with one real `UPDATE` per
        transition — never an in-memory shortcut straight to a terminal
        status. Shared by `create_task_graph` (a fresh graph) and
        `amend_task_graph` (a version+1 graph validated against its full,
        amended node/edge set)."""
        now = self._clock.now()
        graph = TaskGraph(
            graph_id=graph_id,
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            version=version,
            supersedes_id=supersedes_id,
            status="DRAFT",
            planning_mode=planning_mode,
            planner_policy_version=planner_policy_version,
            rationale=rationale,
            open_questions=[],
            graph_hash=graph_hash(tasks, edges),
            created_by_principal=created_by_principal,
            lock_version=1,
            created_at=now,
            updated_at=now,
        )
        await self._repository.insert_task_graph(active.connection, graph)
        validating = await self._advance_status(
            active,
            graph_id,
            from_status="DRAFT",
            to_status="VALIDATING",
            lock_version=1,
        )
        report = validate_graph(
            tasks, edges, approved_requirement_slugs=approved_requirement_slugs
        )
        target: Literal["APPROVED", "REJECTED"] = (
            "APPROVED" if report.valid else "REJECTED"
        )
        return await self._advance_status(
            active,
            graph_id,
            from_status=validating.status,
            to_status=target,
            lock_version=validating.lock_version,
        )

    async def _advance_status(
        self,
        active: PostgresUnitOfWork,
        graph_id: UUID,
        *,
        from_status: str,
        to_status: str,
        lock_version: int,
    ) -> TaskGraph:
        """One guarded `UPDATE ... WHERE lock_version = expected` (Chapter
        3.5) carrying out one legal edge of `GRAPH_TRANSITIONS`."""
        next_status = transition(from_status, to_status, GRAPH_TRANSITIONS)
        now = self._clock.now()
        rowcount = await self._repository.update_task_graph_status(
            active.connection,
            graph_id,
            status=next_status,
            expected_lock_version=lock_version,
            updated_at=now,
        )
        if rowcount != 1:
            refreshed = await self._require_task_graph(active, graph_id)
            raise DdeError(
                "VERSION_CONFLICT",
                "TaskGraph lock_version mismatch",
                retryable=True,
                details={"expected": lock_version, "actual": refreshed.lock_version},
            )
        return await self._require_task_graph(active, graph_id)

    async def _require_task_graph(
        self, active: PostgresUnitOfWork, graph_id: UUID
    ) -> TaskGraph:
        record = await self._repository.get_task_graph(active.connection, graph_id)
        if record is None:
            raise DdeError("GRAPH_INVALID", "Unknown task graph")
        return record
