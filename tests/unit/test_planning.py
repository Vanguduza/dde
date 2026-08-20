"""TaskGraph + template-mode Task Planner (Chapter 4)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from engine.contracts.graph_amendment import GraphAmendment
from engine.contracts.task import Task
from engine.contracts.task_graph_edge import TaskGraphEdge
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.planning.hashing import graph_hash
from engine.planning.validate import validate_graph
from tests.support.harness import build_harness
from tests.unit.test_missions import _mission


def _approved(harness) -> set[str]:
    return set(harness.truth.approved_requirement_slugs(harness.project_id))


def test_template_plan_validates_and_hashes_stably() -> None:
    harness = build_harness()
    mission = _mission(harness)
    graph = harness.planner.plan(
        mission,
        approved_requirement_slugs=_approved(harness),
        created_by_principal=harness.principal_id,
    )
    assert graph.status == "DRAFT"
    assert graph.planning_mode == "template"
    tasks = harness.mission_store.tasks_for_graph(graph.graph_id)
    edges = harness.mission_store.edges_for_graph(graph.graph_id)
    assert graph_hash(tasks, edges) == graph.graph_hash
    shuffled = list(reversed(tasks))
    assert graph_hash(shuffled, list(reversed(edges))) == graph.graph_hash
    report = harness.planner.validate(
        graph.graph_id, approved_requirement_slugs=_approved(harness)
    )
    assert report.valid
    assert harness.mission_store.graphs[graph.graph_id].status == "APPROVED"


def test_cycle_and_untraceable_node_are_rejected() -> None:
    left_id = uuid7()
    right_id = uuid7()
    graph_id = uuid7()
    tenant = uuid7()
    project = uuid7()
    mission = uuid7()
    now = datetime.now(UTC)

    def node(task_id: UUID, refs: list[str]) -> Task:
        return Task(
            task_id=task_id,
            tenant_id=tenant,
            project_id=project,
            mission_id=mission,
            graph_id=graph_id,
            title="n",
            intent="i",
            task_class="implementation",
            requirement_refs=refs,
            feature_refs=[],
            success_criteria=["c"],
            expected_write_scope=["engine/core"],
            expected_read_scope=[],
            blast_radius="local",
            risk_class="low",
            estimated_effort="s",
            autonomy_ceiling=2,
            requires_approval=False,
            status="CREATED",
            lock_version=1,
            created_at=now,
            updated_at=now,
        )

    def edge(source: UUID, dest: UUID) -> TaskGraphEdge:
        return TaskGraphEdge(
            edge_id=uuid7(),
            tenant_id=tenant,
            project_id=project,
            mission_id=mission,
            graph_id=graph_id,
            from_task_id=source,
            to_task_id=dest,
            edge_type="depends_on",
            created_at=now,
            updated_at=now,
        )

    cyclic = validate_graph(
        [node(left_id, ["REQ-A"]), node(right_id, ["REQ-A"])],
        [edge(left_id, right_id), edge(right_id, left_id)],
    )
    assert cyclic.valid is False
    assert "GRAPH_INVALID" in cyclic.error_codes

    untraceable = validate_graph([node(left_id, [])], [])
    assert untraceable.valid is False


def test_overlapping_write_scopes_are_not_scheduled_together() -> None:
    harness = build_harness()
    mission = _mission(harness, intent="two independent branches")
    graph = harness.planner.plan(
        mission,
        approved_requirement_slugs=_approved(harness),
        created_by_principal=harness.principal_id,
        template_id="two_independent_branches",
    )
    harness.planner.validate(
        graph.graph_id, approved_requirement_slugs=_approved(harness)
    )
    approved = harness.mission_store.graphs[graph.graph_id]
    harness.missions.activate_graph(graph.graph_id, lock_version=approved.lock_version)
    tasks = harness.mission_store.tasks_for_graph(graph.graph_id)
    left = next(task for task in tasks if task.title == "Implement left branch")
    right = next(task for task in tasks if task.title == "Implement right branch")
    cloned_scope = right.model_copy(
        update={"expected_write_scope": list(left.expected_write_scope)}
    )
    harness.mission_store.tasks[right.task_id] = cloned_scope
    scheduled = harness.planner.schedule(graph.graph_id)
    impls = [
        task
        for task in scheduled
        if task.title in {"Implement left branch", "Implement right branch"}
    ]
    assert len(impls) == 1


def test_blocked_branch_does_not_stop_independent_work() -> None:
    harness = build_harness()
    mission = _mission(harness, intent="two independent branches")
    graph = harness.planner.plan(
        mission,
        approved_requirement_slugs=_approved(harness),
        created_by_principal=harness.principal_id,
        template_id="two_independent_branches",
    )
    harness.planner.validate(
        graph.graph_id, approved_requirement_slugs=_approved(harness)
    )
    approved = harness.mission_store.graphs[graph.graph_id]
    harness.missions.activate_graph(graph.graph_id, lock_version=approved.lock_version)
    tasks = {
        task.title: task
        for task in harness.mission_store.tasks_for_graph(graph.graph_id)
    }
    decision = tasks["Architecture decision"]
    harness.missions.transition_task(
        decision.task_id, "BLOCKED_ON_DECISION", lock_version=decision.lock_version
    )
    assert harness.planner.independent_progress_possible(
        graph.graph_id, decision.task_id
    )
    scheduled = harness.planner.schedule(graph.graph_id)
    titles = {task.title for task in scheduled}
    assert "Implement left branch" in titles
    assert "Implement right branch" not in titles


def test_out_of_scope_amendment_is_denied() -> None:
    harness = build_harness()
    mission = _mission(harness)
    started = harness.missions.start(
        mission.mission_id, lock_version=mission.lock_version
    )
    graph = harness.planner.plan(
        started,
        approved_requirement_slugs=_approved(harness),
        created_by_principal=harness.principal_id,
    )
    harness.planner.validate(
        graph.graph_id, approved_requirement_slugs=_approved(harness)
    )
    approved = harness.mission_store.graphs[graph.graph_id]
    active = harness.missions.activate_graph(
        graph.graph_id, lock_version=approved.lock_version
    )
    amendment = GraphAmendment(
        amendment_id=uuid7(),
        graph_id=active.graph_id,
        proposed_by="worker-run",
        amendment_type="widen_scope",
        justification="drive-by refactor",
        evidence_refs=[],
        affected_task_ids=[],
        requested_write_scope=["secret/other-project"],
    )
    with pytest.raises(DdeError) as captured:
        harness.planner.amend(
            active.graph_id, amendment, mission=started, reason="out of scope"
        )
    assert captured.value.error_code == "SCOPE_VIOLATION"


def test_replan_refused_when_effect_unknown() -> None:
    harness = build_harness()
    mission = _mission(harness)
    graph = harness.planner.plan(
        mission,
        approved_requirement_slugs=_approved(harness),
        created_by_principal=harness.principal_id,
    )
    harness.planner.validate(
        graph.graph_id, approved_requirement_slugs=_approved(harness)
    )
    approved = harness.mission_store.graphs[graph.graph_id]
    harness.missions.activate_graph(graph.graph_id, lock_version=approved.lock_version)
    task = harness.mission_store.tasks_for_graph(graph.graph_id)[0]
    with pytest.raises(DdeError) as captured:
        harness.planner.replan(
            graph.graph_id,
            trigger="operator",
            unknown_effect_task_ids={task.task_id},
            in_flight_state={task.task_id: "EXECUTING"},
        )
    assert captured.value.error_code == "EFFECT_UNKNOWN"


def test_effort_l_is_decomposition_failure() -> None:
    now = datetime.now(UTC)
    task = Task(
        task_id=uuid7(),
        tenant_id=uuid7(),
        project_id=uuid7(),
        mission_id=uuid7(),
        graph_id=uuid7(),
        title="too big",
        intent="do everything",
        task_class="implementation",
        requirement_refs=["REQ-A"],
        feature_refs=[],
        success_criteria=["one"],
        expected_write_scope=["engine/core"],
        expected_read_scope=[],
        blast_radius="local",
        risk_class="low",
        estimated_effort="l",
        autonomy_ceiling=2,
        requires_approval=False,
        status="CREATED",
        lock_version=1,
        created_at=now,
        updated_at=now,
    )
    report = validate_graph([task], [])
    assert "DECOMPOSITION_REQUIRED" in report.error_codes
