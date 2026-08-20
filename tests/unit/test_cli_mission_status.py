"""Unit tests for `interfaces.cli.mission_status`'s pure rendering logic
(Chapter 19.1 unit test type) -- hand-built `MissionStatus` values, no
database, mirroring `tests/unit/test_cli_mission_trace.py`'s pattern for
its own pure-logic module.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from engine.contracts.mission import Mission
from engine.contracts.task import Task
from engine.contracts.task_graph import TaskGraph
from interfaces.cli.mission_status import MissionStatus, render_mission_status

NOW = datetime.now(UTC)


def _mission() -> Mission:
    return Mission(
        mission_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        slug="mission-status-unit",
        title="Unit test mission",
        intent="Exercise the mission-status renderer",
        success_definition="dde mission status shows real task counts",
        scope=["engine"],
        requirement_refs=[],
        status="ACTIVE",
        autonomy_ceiling=2,
        lock_version=3,
        created_at=NOW,
        updated_at=NOW,
    )


def _task(mission: Mission, graph_id: UUID, *, status: str, title: str) -> Task:
    return Task(
        task_id=uuid4(),
        tenant_id=mission.tenant_id,
        project_id=mission.project_id,
        mission_id=mission.mission_id,
        graph_id=graph_id,
        title=title,
        intent="Exercise the mission-status renderer",
        task_class="implementation",
        requirement_refs=[],
        feature_refs=[],
        success_criteria=["Behaviour is implemented"],
        expected_write_scope=["engine"],
        expected_read_scope=["engine"],
        blast_radius="local",
        risk_class="low",
        estimated_effort="s",
        autonomy_ceiling=2,
        requires_approval=False,
        status=status,
        lock_version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _task_graph(mission: Mission, graph_id: UUID, *, version: int) -> TaskGraph:
    return TaskGraph(
        graph_id=graph_id,
        tenant_id=mission.tenant_id,
        project_id=mission.project_id,
        mission_id=mission.mission_id,
        version=version,
        status="APPROVED",
        planning_mode="template",
        planner_policy_version="planner-v1",
        rationale="unit test fixture",
        open_questions=[],
        graph_hash="d" * 64,
        created_by_principal=uuid4(),
        lock_version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def test_render_mission_status_counts_tasks_by_status() -> None:
    mission = _mission()
    graph_id = uuid4()
    tasks = [
        _task(mission, graph_id, status="COMPLETED", title="Task A"),
        _task(mission, graph_id, status="COMPLETED", title="Task B"),
        _task(mission, graph_id, status="CREATED", title="Task C"),
    ]
    status = MissionStatus(
        mission=mission,
        tasks=tasks,
        task_graphs=[_task_graph(mission, graph_id, version=1)],
    )

    output = render_mission_status(status)

    assert str(mission.mission_id) in output
    assert "status=ACTIVE" in output
    assert "Tasks: 3 total" in output
    assert "COMPLETED: 2" in output
    assert "CREATED: 1" in output
    assert f"TaskGraph {graph_id}  v1" in output


def test_render_mission_status_handles_a_mission_with_no_tasks_yet() -> None:
    mission = _mission()
    status = MissionStatus(mission=mission, tasks=[], task_graphs=[])

    output = render_mission_status(status)

    assert "Tasks: 0 total" in output
    assert "none recorded" in output
    assert "TaskGraphs: none recorded" in output
