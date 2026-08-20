"""Mission Kernel: mission and task lifecycle only (Chapter 2.6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from engine.contracts.mission import Mission
from engine.contracts.task import Task
from engine.contracts.task_graph import TaskGraph
from engine.contracts.task_graph_edge import TaskGraphEdge
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.engine import EventEngine
from engine.missions.states import (
    GRAPH_TRANSITIONS,
    IN_FLIGHT_TASK,
    MISSION_TRANSITIONS,
    TASK_TRANSITIONS,
    TERMINAL_MISSION,
    transition,
)


@dataclass
class MissionStore:
    missions: dict[UUID, Mission] = field(default_factory=dict)
    graphs: dict[UUID, TaskGraph] = field(default_factory=dict)
    tasks: dict[UUID, Task] = field(default_factory=dict)
    edges: dict[UUID, TaskGraphEdge] = field(default_factory=dict)

    def tasks_for_graph(self, graph_id: UUID) -> list[Task]:
        return [item for item in self.tasks.values() if item.graph_id == graph_id]

    def edges_for_graph(self, graph_id: UUID) -> list[TaskGraphEdge]:
        return [item for item in self.edges.values() if item.graph_id == graph_id]


class MissionKernel:
    def __init__(
        self,
        store: MissionStore,
        events: EventEngine,
        clock: Clock | None = None,
    ) -> None:
        self._store = store
        self._events = events
        self._clock = clock or SystemClock()

    def commit_mission(
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
        expected_lock_version: int | None = None,
    ) -> Mission:
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
        if expected_lock_version is not None:
            raise DdeError("VERSION_CONFLICT", "Create does not accept a lock token")
        self._store.missions[mission.mission_id] = mission
        self._events.append(
            event_type="MissionCommitted",
            aggregate_type="mission",
            aggregate_id=mission.mission_id,
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission.mission_id,
            payload={"slug": slug, "status": mission.status},
        )
        return mission

    def start(self, mission_id: UUID, *, lock_version: int) -> Mission:
        return self._transition_mission(mission_id, "ACTIVE", lock_version)

    def enter_partial(self, mission_id: UUID, *, lock_version: int) -> Mission:
        return self._transition_mission(mission_id, "PARTIAL", lock_version)

    def pause(self, mission_id: UUID, *, lock_version: int) -> Mission:
        return self._transition_mission(mission_id, "PAUSED", lock_version)

    def resume(self, mission_id: UUID, *, lock_version: int) -> Mission:
        mission = self._require_mission(mission_id)
        if mission.status == "PAUSED" and self._has_blocked_branch(mission_id):
            return self._transition_mission(mission_id, "PARTIAL", lock_version)
        return self._transition_mission(mission_id, "ACTIVE", lock_version)

    def cancel(self, mission_id: UUID, *, lock_version: int) -> Mission:
        return self._transition_mission(mission_id, "CANCELLED", lock_version)

    def complete(self, mission_id: UUID, *, lock_version: int) -> Mission:
        self._require_mission(mission_id)
        graph = self._active_graph(mission_id)
        if graph is not None:
            remaining = [
                task
                for task in self._store.tasks_for_graph(graph.graph_id)
                if task.status not in {"COMPLETED", "RETIRED", "SUPERSEDED"}
            ]
            if remaining:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Mission cannot COMPLETE while non-retired nodes remain open",
                    details={"open_tasks": [str(item.task_id) for item in remaining]},
                )
        return self._transition_mission(mission_id, "COMPLETED", lock_version)

    def fail(self, mission_id: UUID, *, lock_version: int) -> Mission:
        return self._transition_mission(mission_id, "FAILED", lock_version)

    def transition_task(self, task_id: UUID, target: str, *, lock_version: int) -> Task:
        task = self._require_task(task_id)
        if task.lock_version != lock_version:
            raise DdeError(
                "VERSION_CONFLICT",
                "Task lock_version mismatch",
                retryable=True,
                details={"expected": lock_version, "actual": task.lock_version},
            )
        now = self._clock.now()
        updated = task.model_copy(
            update={
                "status": transition(task.status, target, TASK_TRANSITIONS),
                "lock_version": task.lock_version + 1,
                "updated_at": now,
            }
        )
        self._store.tasks[task_id] = updated
        self._events.append(
            event_type="TaskTransitioned",
            aggregate_type="task",
            aggregate_id=task_id,
            tenant_id=task.tenant_id,
            project_id=task.project_id,
            mission_id=task.mission_id,
            task_id=task_id,
            payload={"from": task.status, "to": updated.status},
        )
        self._propagate_failure(updated)
        return updated

    def activate_graph(self, graph_id: UUID, *, lock_version: int) -> TaskGraph:
        graph = self._require_graph(graph_id)
        if graph.lock_version != lock_version:
            raise DdeError(
                "VERSION_CONFLICT",
                "TaskGraph lock_version mismatch",
                retryable=True,
            )
        now = self._clock.now()
        updated = graph.model_copy(
            update={
                "status": transition(graph.status, "ACTIVE", GRAPH_TRANSITIONS),
                "lock_version": graph.lock_version + 1,
                "updated_at": now,
            }
        )
        self._store.graphs[graph_id] = updated
        self.refresh_task_readiness(graph_id)
        return updated

    def refresh_task_readiness(self, graph_id: UUID) -> None:
        tasks = {item.task_id: item for item in self._store.tasks_for_graph(graph_id)}
        edges = self._store.edges_for_graph(graph_id)
        for task in list(tasks.values()):
            if task.status not in {"CREATED", "BLOCKED"}:
                continue
            blocked = False
            for edge in edges:
                if edge.to_task_id != task.task_id:
                    continue
                if edge.edge_type not in {"depends_on", "produces_contract_for"}:
                    continue
                predecessor = tasks[edge.from_task_id]
                if edge.edge_type == "depends_on" and predecessor.status != "COMPLETED":
                    blocked = True
                if (
                    edge.edge_type == "produces_contract_for"
                    and predecessor.status != "COMPLETED"
                ):
                    blocked = True
            target = "BLOCKED" if blocked else "READY"
            if task.status == target:
                continue
            self._store.tasks[task.task_id] = task.model_copy(
                update={
                    "status": transition(task.status, target, TASK_TRANSITIONS),
                    "lock_version": task.lock_version + 1,
                    "updated_at": self._clock.now(),
                }
            )

    def in_flight_tasks(self, graph_id: UUID) -> list[Task]:
        return [
            task
            for task in self._store.tasks_for_graph(graph_id)
            if task.status in IN_FLIGHT_TASK
        ]

    def _transition_mission(
        self, mission_id: UUID, target: str, lock_version: int
    ) -> Mission:
        mission = self._require_mission(mission_id)
        if mission.lock_version != lock_version:
            raise DdeError(
                "VERSION_CONFLICT",
                "Mission lock_version mismatch",
                retryable=True,
                details={"expected": lock_version, "actual": mission.lock_version},
            )
        now = self._clock.now()
        updated = mission.model_copy(
            update={
                "status": transition(mission.status, target, MISSION_TRANSITIONS),
                "lock_version": mission.lock_version + 1,
                "updated_at": now,
            }
        )
        self._store.missions[mission_id] = updated
        self._events.append(
            event_type="MissionTransitioned",
            aggregate_type="mission",
            aggregate_id=mission_id,
            tenant_id=mission.tenant_id,
            project_id=mission.project_id,
            mission_id=mission_id,
            payload={"from": mission.status, "to": updated.status},
        )
        return updated

    def _propagate_failure(self, task: Task) -> None:
        if task.status not in {"RETIRED"}:
            return
        mission = self._require_mission(task.mission_id)
        if mission.status in TERMINAL_MISSION:
            return
        graph = self._active_graph(task.mission_id)
        if graph is None:
            return
        independent = [
            item
            for item in self._store.tasks_for_graph(graph.graph_id)
            if item.task_id != task.task_id
            and item.status not in {"COMPLETED", "RETIRED", "SUPERSEDED", "BLOCKED"}
        ]
        if independent and mission.status == "ACTIVE":
            self._transition_mission(
                mission.mission_id, "PARTIAL", mission.lock_version
            )

    def _has_blocked_branch(self, mission_id: UUID) -> bool:
        graph = self._active_graph(mission_id)
        if graph is None:
            return False
        return any(
            task.status == "BLOCKED_ON_DECISION"
            for task in self._store.tasks_for_graph(graph.graph_id)
        )

    def _active_graph(self, mission_id: UUID) -> TaskGraph | None:
        matches = [
            graph
            for graph in self._store.graphs.values()
            if graph.mission_id == mission_id and graph.status == "ACTIVE"
        ]
        return matches[0] if matches else None

    def _require_mission(self, mission_id: UUID) -> Mission:
        mission = self._store.missions.get(mission_id)
        if mission is None:
            raise DdeError("POLICY_DENIED", "Unknown mission")
        return mission

    def _require_task(self, task_id: UUID) -> Task:
        task = self._store.tasks.get(task_id)
        if task is None:
            raise DdeError("POLICY_DENIED", "Unknown task")
        return task

    def _require_graph(self, graph_id: UUID) -> TaskGraph:
        graph = self._store.graphs.get(graph_id)
        if graph is None:
            raise DdeError("GRAPH_INVALID", "Unknown task graph")
        return graph
