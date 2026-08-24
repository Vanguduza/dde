"""Task Planner in template mode (Chapter 4.3)."""

from __future__ import annotations

from uuid import UUID

from engine.contracts.graph_amendment import GraphAmendment
from engine.contracts.mission import Mission
from engine.contracts.mission_template import MissionTemplate
from engine.contracts.replan_decision import ReplanDecision
from engine.contracts.task import Task
from engine.contracts.task_graph import TaskGraph
from engine.contracts.task_graph_edge import TaskGraphEdge
from engine.contracts.validation_report import ValidationReport
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.missions.kernel import MissionKernel, MissionStore
from engine.missions.states import GRAPH_TRANSITIONS, IN_FLIGHT_TASK, transition
from engine.planning.hashing import graph_hash
from engine.planning.templates import TEMPLATES, select_template
from engine.planning.validate import (
    blocked_on_decision,
    dependents,
    in_scope,
    ready_predecessors_complete,
    scopes_overlap,
    validate_graph,
)
from engine.recovery.matrix import classify_dispositions

PLANNER_POLICY_VERSION = "template-v1"
DEFAULT_MISSION_CONCURRENCY = 4


class TaskPlanner:
    def __init__(
        self,
        missions: MissionKernel,
        store: MissionStore,
        clock: Clock | None = None,
    ) -> None:
        self._missions = missions
        self._store = store
        self._clock = clock or SystemClock()

    def plan(
        self,
        mission: Mission,
        *,
        approved_requirement_slugs: set[str],
        created_by_principal: UUID,
        template_id: str | None = None,
    ) -> TaskGraph:
        chosen = template_id or select_template(mission)
        if chosen is None or chosen not in TEMPLATES:
            raise DdeError(
                "DECOMPOSITION_REQUIRED",
                "No registered mission template matches this mission",
            )
        missing = [
            slug
            for slug in mission.requirement_refs
            if slug not in approved_requirement_slugs
        ]
        if missing:
            raise DdeError(
                "GRAPH_INVALID",
                "Mission requirement refs are not approved Project Truth",
                details={"missing": missing},
            )
        graph_id = uuid7()
        planned = TEMPLATES[chosen](mission, graph_id, self._clock)
        digest = graph_hash(planned.tasks, planned.edges)
        now = self._clock.now()
        graph = TaskGraph(
            graph_id=graph_id,
            tenant_id=mission.tenant_id,
            project_id=mission.project_id,
            mission_id=mission.mission_id,
            version=1,
            supersedes_id=None,
            status="DRAFT",
            planning_mode="template",
            planner_policy_version=PLANNER_POLICY_VERSION,
            rationale=planned.rationale,
            open_questions=[],
            graph_hash=digest,
            created_by_principal=created_by_principal,
            lock_version=1,
            created_at=now,
            updated_at=now,
        )
        self._store.graphs[graph.graph_id] = graph
        for task in planned.tasks:
            self._store.tasks[task.task_id] = task
        for edge in planned.edges:
            self._store.edges[edge.edge_id] = edge
        return graph

    def plan_from_template(
        self,
        mission: Mission,
        template: MissionTemplate,
        *,
        approved_requirement_slugs: set[str],
        created_by_principal: UUID,
    ) -> TaskGraph:
        """Instantiate a DURABLE registered template (Chapter 4.3:
        "first-class registry objects with their own version") into a
        task graph. Provenance is recorded on the graph itself: the
        rationale names the template key and content-hashed version that
        produced it, so every graph remains explainable by the exact
        registry row it came from. The deterministic planner policy is
        unchanged -- only decomposition source differs from `plan`."""
        if template.status != "ACTIVE":
            raise DdeError(
                "POLICY_DENIED",
                "Retired templates never instantiate; re-register a new "
                "version instead (Chapter 3.10)",
                details={
                    "template_key": template.template_key,
                    "template_version": template.template_version,
                    "status": template.status,
                },
            )
        missing = [
            slug
            for slug in mission.requirement_refs
            if slug not in approved_requirement_slugs
        ]
        if missing:
            raise DdeError(
                "GRAPH_INVALID",
                "Mission requirement refs are not approved Project Truth",
                details={"missing": missing},
            )

        graph_id = uuid7()
        now = self._clock.now()
        by_key: dict[str, Task] = {}
        tasks: list[Task] = []
        for node in template.nodes:
            task = Task(
                task_id=uuid7(),
                tenant_id=mission.tenant_id,
                project_id=mission.project_id,
                mission_id=mission.mission_id,
                graph_id=graph_id,
                parent_task_id=None,  # resolved below once parents exist
                title=node.title,
                intent=node.intent,
                task_class=node.task_class,
                requirement_refs=list(mission.requirement_refs),
                feature_refs=[],
                success_criteria=list(node.success_criteria),
                expected_write_scope=list(node.write_scope),
                expected_read_scope=list(node.read_scope or node.write_scope),
                blast_radius=node.blast_radius or "local",
                risk_class=node.risk_class or "low",
                estimated_effort=node.estimated_effort,
                autonomy_ceiling=min(mission.autonomy_ceiling, 3),
                requires_approval=False,
                verification_profile_ref="unit",
                status="CREATED",
                lock_version=1,
                created_at=now,
                updated_at=now,
            )
            by_key[node.node_key] = task
            tasks.append(task)
        for node in template.nodes:
            parent_key = node.parent_node_key
            if parent_key is not None:
                parent = by_key.get(parent_key)
                if parent is None:
                    raise DdeError(
                        "GRAPH_INVALID",
                        f"Template parent node key {parent_key} unknown",
                        details={"template_key": template.template_key},
                    )
                by_key[node.node_key].parent_task_id = parent.task_id

        graph_edges: list[TaskGraphEdge] = []
        for template_edge in template.edges:
            source = by_key[template_edge.from_node_key]
            dest = by_key[template_edge.to_node_key]
            graph_edges.append(
                TaskGraphEdge(
                    edge_id=uuid7(),
                    tenant_id=mission.tenant_id,
                    project_id=mission.project_id,
                    mission_id=mission.mission_id,
                    graph_id=graph_id,
                    from_task_id=source.task_id,
                    to_task_id=dest.task_id,
                    edge_type=template_edge.edge_type,
                    contract_ref=template_edge.contract_ref,
                    created_at=now,
                    updated_at=now,
                )
            )

        digest = graph_hash(tasks, graph_edges)
        graph = TaskGraph(
            graph_id=graph_id,
            tenant_id=mission.tenant_id,
            project_id=mission.project_id,
            mission_id=mission.mission_id,
            version=1,
            supersedes_id=None,
            status="DRAFT",
            planning_mode="template",
            planner_policy_version=PLANNER_POLICY_VERSION,
            rationale=(
                f"template:{template.template_key}@{template.template_version[:16]}"
            ),
            open_questions=[],
            graph_hash=digest,
            created_by_principal=created_by_principal,
            lock_version=1,
            created_at=now,
            updated_at=now,
        )
        self._store.graphs[graph.graph_id] = graph
        for task in tasks:
            self._store.tasks[task.task_id] = task
        for edge in graph_edges:
            self._store.edges[edge.edge_id] = edge
        return graph

    def validate(
        self, graph_id: UUID, *, approved_requirement_slugs: set[str]
    ) -> ValidationReport:
        graph = self._require_graph(graph_id)
        if graph.status == "DRAFT":
            now = self._clock.now()
            self._store.graphs[graph_id] = graph.model_copy(
                update={
                    "status": transition(graph.status, "VALIDATING", GRAPH_TRANSITIONS),
                    "lock_version": graph.lock_version + 1,
                    "updated_at": now,
                }
            )
            graph = self._store.graphs[graph_id]
        tasks = self._store.tasks_for_graph(graph_id)
        edges = self._store.edges_for_graph(graph_id)
        report = validate_graph(
            tasks,
            edges,
            expected_hash=graph.graph_hash,
            approved_requirement_slugs=approved_requirement_slugs,
        )
        if report.valid:
            self._store.graphs[graph_id] = graph.model_copy(
                update={
                    "status": transition(graph.status, "APPROVED", GRAPH_TRANSITIONS),
                    "lock_version": graph.lock_version + 1,
                    "updated_at": self._clock.now(),
                }
            )
        else:
            self._store.graphs[graph_id] = graph.model_copy(
                update={
                    "status": transition(graph.status, "REJECTED", GRAPH_TRANSITIONS),
                    "lock_version": graph.lock_version + 1,
                    "updated_at": self._clock.now(),
                }
            )
        return report

    def amend(
        self,
        graph_id: UUID,
        amendment: GraphAmendment,
        *,
        mission: Mission,
        reason: str,
    ) -> TaskGraph:
        graph = self._require_graph(graph_id)
        if amendment.amendment_type == "widen_scope":
            extra = [
                path
                for path in amendment.requested_write_scope
                if not in_scope(path, mission.scope)
            ]
            if extra:
                raise DdeError(
                    "SCOPE_VIOLATION",
                    "Out-of-scope amendment denied",
                    details={"paths": extra, "reason": reason},
                )
        now = self._clock.now()
        amending = graph.model_copy(
            update={
                "status": transition(graph.status, "AMENDING", GRAPH_TRANSITIONS),
                "lock_version": graph.lock_version + 1,
                "updated_at": now,
            }
        )
        self._store.graphs[graph_id] = amending
        if amendment.amendment_type == "retire_task":
            for task_id in amendment.affected_task_ids:
                task = self._store.tasks[task_id]
                self._missions.transition_task(
                    task_id, "RETIRED", lock_version=task.lock_version
                )
        restored = amending.model_copy(
            update={
                "status": transition("AMENDING", "ACTIVE", GRAPH_TRANSITIONS),
                "lock_version": amending.lock_version + 1,
                "updated_at": self._clock.now(),
            }
        )
        self._store.graphs[graph_id] = restored
        return restored

    def schedule(
        self,
        graph_id: UUID,
        *,
        capacity: int = DEFAULT_MISSION_CONCURRENCY,
        in_flight: list[Task] | None = None,
    ) -> list[Task]:
        tasks = self._store.tasks_for_graph(graph_id)
        edges = self._store.edges_for_graph(graph_id)
        running = in_flight or [task for task in tasks if task.status in IN_FLIGHT_TASK]
        held_scopes = [scope for task in running for scope in task.expected_write_scope]
        ready: list[Task] = []
        for task in sorted(tasks, key=lambda item: str(item.task_id)):
            if task.status not in {"READY", "CREATED"}:
                continue
            if blocked_on_decision(task, edges, tasks):
                continue
            if not ready_predecessors_complete(task, tasks, edges):
                continue
            if scopes_overlap(task.expected_write_scope, held_scopes):
                continue
            if any(
                scopes_overlap(task.expected_write_scope, chosen.expected_write_scope)
                for chosen in ready
            ):
                continue
            ready.append(task)
            held_scopes.extend(task.expected_write_scope)
            if len(running) + len(ready) >= capacity:
                break
        return ready

    def replan(
        self,
        graph_id: UUID,
        *,
        trigger: str,
        unknown_effect_task_ids: set[UUID],
        in_flight_state: dict[UUID, str],
    ) -> ReplanDecision:
        tasks = self._store.tasks_for_graph(graph_id)
        affected = set(in_flight_state) | {task.task_id for task in tasks}
        if unknown_effect_task_ids & affected:
            raise DdeError(
                "EFFECT_UNKNOWN",
                "Replanning refused until unreconciled external effects are resolved",
            )
        graph = self._require_graph(graph_id)
        self._store.graphs[graph_id] = graph.model_copy(
            update={
                "status": transition(graph.status, "REPLANNING", GRAPH_TRANSITIONS),
                "lock_version": graph.lock_version + 1,
                "updated_at": self._clock.now(),
            }
        )
        dispositions, explanations = classify_dispositions(
            task_ids=[task.task_id for task in tasks],
            statuses={task.task_id: task.status for task in tasks},
            in_flight_ids=set(in_flight_state),
            completed_ids={
                task.task_id for task in tasks if task.status == "COMPLETED"
            },
            integrated_ids={
                task.task_id for task in tasks if task.status == "COMPLETED"
            },
            trigger=trigger,
        )
        self._store.graphs[graph_id] = self._store.graphs[graph_id].model_copy(
            update={
                "status": transition(
                    self._store.graphs[graph_id].status, "SUPERSEDED", GRAPH_TRANSITIONS
                ),
                "lock_version": self._store.graphs[graph_id].lock_version + 1,
                "updated_at": self._clock.now(),
            }
        )
        return ReplanDecision(
            graph_id=graph_id,
            trigger=trigger,
            dispositions=dispositions,
            explanations=explanations,
        )

    def independent_progress_possible(
        self, graph_id: UUID, blocked_task_id: UUID
    ) -> bool:
        edges = self._store.edges_for_graph(graph_id)
        blocked_dependents = dependents(blocked_task_id, edges)
        for task in self._store.tasks_for_graph(graph_id):
            if task.task_id == blocked_task_id or task.task_id in blocked_dependents:
                continue
            if task.status not in {"COMPLETED", "RETIRED", "SUPERSEDED"}:
                return True
        return False

    def _require_graph(self, graph_id: UUID) -> TaskGraph:
        graph = self._store.graphs.get(graph_id)
        if graph is None:
            raise DdeError("GRAPH_INVALID", "Unknown task graph")
        return graph
