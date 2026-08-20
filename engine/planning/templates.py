"""Registered mission templates for Stage 1 template-mode planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from engine.contracts.mission import Mission
from engine.contracts.task import Task
from engine.contracts.task_graph_edge import TaskGraphEdge
from engine.core.clock import Clock
from engine.core.ids import uuid7

TaskClass = Literal[
    "discovery",
    "specification",
    "decision",
    "enabling",
    "implementation",
    "integration",
    "verification",
    "repair",
    "documentation",
]
EdgeType = Literal[
    "depends_on",
    "produces_contract_for",
    "verifies",
    "repairs",
    "blocks_on_decision",
]


@dataclass(frozen=True)
class PlannedGraph:
    tasks: list[Task]
    edges: list[TaskGraphEdge]
    rationale: str
    template_id: str


def _task(
    *,
    mission: Mission,
    graph_id: UUID,
    clock: Clock,
    title: str,
    intent: str,
    task_class: TaskClass,
    write_scope: list[str],
    success_criteria: list[str],
    parent_task_id: UUID | None = None,
) -> Task:
    now = clock.now()
    return Task(
        task_id=uuid7(),
        tenant_id=mission.tenant_id,
        project_id=mission.project_id,
        mission_id=mission.mission_id,
        graph_id=graph_id,
        parent_task_id=parent_task_id,
        title=title,
        intent=intent,
        task_class=task_class,
        requirement_refs=list(mission.requirement_refs),
        feature_refs=[],
        success_criteria=success_criteria,
        expected_write_scope=write_scope,
        expected_read_scope=write_scope,
        blast_radius="local",
        risk_class="low",
        estimated_effort="s",
        autonomy_ceiling=min(mission.autonomy_ceiling, 3),
        requires_approval=False,
        verification_profile_ref="unit",
        status="CREATED",
        lock_version=1,
        created_at=now,
        updated_at=now,
    )


def _edge(
    *,
    mission: Mission,
    graph_id: UUID,
    clock: Clock,
    source: Task,
    dest: Task,
    edge_type: EdgeType,
    contract_ref: str | None = None,
) -> TaskGraphEdge:
    now = clock.now()
    return TaskGraphEdge(
        edge_id=uuid7(),
        tenant_id=mission.tenant_id,
        project_id=mission.project_id,
        mission_id=mission.mission_id,
        graph_id=graph_id,
        from_task_id=source.task_id,
        to_task_id=dest.task_id,
        edge_type=edge_type,
        contract_ref=contract_ref,
        created_at=now,
        updated_at=now,
    )


def add_endpoint_template(
    mission: Mission, graph_id: UUID, clock: Clock
) -> PlannedGraph:
    spec = _task(
        mission=mission,
        graph_id=graph_id,
        clock=clock,
        title="Specify endpoint contract",
        intent="Commit the HTTP contract before implementation",
        task_class="specification",
        write_scope=["schemas/api"],
        success_criteria=["Endpoint schema committed under schemas/api"],
    )
    impl = _task(
        mission=mission,
        graph_id=graph_id,
        clock=clock,
        title="Implement endpoint",
        intent=mission.intent,
        task_class="implementation",
        write_scope=["engine/gateway"],
        success_criteria=["Handler returns the contracted payload"],
    )
    verify = _task(
        mission=mission,
        graph_id=graph_id,
        clock=clock,
        title="Verify endpoint",
        intent="Independently verify the endpoint",
        task_class="verification",
        write_scope=["tests/unit"],
        success_criteria=["Contract test covers the endpoint"],
    )
    edges = [
        _edge(
            mission=mission,
            graph_id=graph_id,
            clock=clock,
            source=spec,
            dest=impl,
            edge_type="produces_contract_for",
            contract_ref="schemas/api",
        ),
        _edge(
            mission=mission,
            graph_id=graph_id,
            clock=clock,
            source=spec,
            dest=impl,
            edge_type="depends_on",
        ),
        _edge(
            mission=mission,
            graph_id=graph_id,
            clock=clock,
            source=impl,
            dest=verify,
            edge_type="depends_on",
        ),
        _edge(
            mission=mission,
            graph_id=graph_id,
            clock=clock,
            source=verify,
            dest=impl,
            edge_type="verifies",
        ),
    ]
    return PlannedGraph(
        tasks=[spec, impl, verify],
        edges=edges,
        rationale="template:add_endpoint",
        template_id="add_endpoint",
    )


def two_branch_template(mission: Mission, graph_id: UUID, clock: Clock) -> PlannedGraph:
    """Independent branches used by Chapter 4.11 blocked-approval fixture."""
    left = _task(
        mission=mission,
        graph_id=graph_id,
        clock=clock,
        title="Implement left branch",
        intent="Independent left-hand work",
        task_class="implementation",
        write_scope=["engine/truth"],
        success_criteria=["Left branch observable behaviour holds"],
    )
    left_verify = _task(
        mission=mission,
        graph_id=graph_id,
        clock=clock,
        title="Verify left branch",
        intent="Verify left-hand work",
        task_class="verification",
        write_scope=["tests/unit"],
        success_criteria=["Left branch tests pass"],
    )
    decision = _task(
        mission=mission,
        graph_id=graph_id,
        clock=clock,
        title="Architecture decision",
        intent="Human decision for the right branch",
        task_class="decision",
        write_scope=["docs/truth"],
        success_criteria=["Decision recorded as an EDR"],
    )
    right = _task(
        mission=mission,
        graph_id=graph_id,
        clock=clock,
        title="Implement right branch",
        intent="Work gated on the decision",
        task_class="implementation",
        write_scope=["engine/missions"],
        success_criteria=["Right branch observable behaviour holds"],
    )
    right_verify = _task(
        mission=mission,
        graph_id=graph_id,
        clock=clock,
        title="Verify right branch",
        intent="Verify right-hand work",
        task_class="verification",
        write_scope=["tests/contract"],
        success_criteria=["Right branch tests pass"],
    )
    edges = [
        _edge(
            mission=mission,
            graph_id=graph_id,
            clock=clock,
            source=decision,
            dest=right,
            edge_type="blocks_on_decision",
        ),
        _edge(
            mission=mission,
            graph_id=graph_id,
            clock=clock,
            source=left,
            dest=left_verify,
            edge_type="depends_on",
        ),
        _edge(
            mission=mission,
            graph_id=graph_id,
            clock=clock,
            source=left_verify,
            dest=left,
            edge_type="verifies",
        ),
        _edge(
            mission=mission,
            graph_id=graph_id,
            clock=clock,
            source=right,
            dest=right_verify,
            edge_type="depends_on",
        ),
        _edge(
            mission=mission,
            graph_id=graph_id,
            clock=clock,
            source=right_verify,
            dest=right,
            edge_type="verifies",
        ),
    ]
    return PlannedGraph(
        tasks=[left, left_verify, decision, right, right_verify],
        edges=edges,
        rationale="template:two_independent_branches",
        template_id="two_independent_branches",
    )


TEMPLATES = {
    "add_endpoint": add_endpoint_template,
    "two_independent_branches": two_branch_template,
}


def select_template(mission: Mission) -> str | None:
    text = f"{mission.title} {mission.intent}".lower()
    if "two branch" in text or "independent branch" in text:
        return "two_independent_branches"
    if "endpoint" in text or "/health" in text or "route" in text:
        return "add_endpoint"
    return None
