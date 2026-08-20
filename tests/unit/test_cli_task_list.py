"""Unit tests for `interfaces.cli.task_list`'s pure rendering logic
(Chapter 19.1 unit test type) -- hand-built `TaskListing` values, no
database.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from engine.contracts.mission import Mission
from engine.contracts.task import Task
from interfaces.cli.task_list import TaskListing, render_task_listing

NOW = datetime.now(UTC)


def _mission() -> Mission:
    return Mission(
        mission_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        slug="task-list-unit",
        title="Unit test mission",
        intent="Exercise the task-list renderer",
        success_definition="dde task list shows real tasks",
        scope=["engine"],
        requirement_refs=[],
        status="ACTIVE",
        autonomy_ceiling=2,
        lock_version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _task(mission: Mission, *, title: str, status: str) -> Task:
    return Task(
        task_id=uuid4(),
        tenant_id=mission.tenant_id,
        project_id=mission.project_id,
        mission_id=mission.mission_id,
        graph_id=uuid4(),
        title=title,
        intent="Exercise the task-list renderer",
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


def test_render_task_listing_lists_every_task() -> None:
    mission = _mission()
    tasks = [
        _task(mission, title="First task", status="READY"),
        _task(mission, title="Second task", status="CREATED"),
    ]
    listing = TaskListing(mission=mission, tasks=tasks)

    output = render_task_listing(listing)

    assert str(mission.mission_id) in output
    assert "Total: 2 task(s)" in output
    for task in tasks:
        assert str(task.task_id) in output
        assert task.title in output
        assert f"status={task.status}" in output


def test_render_task_listing_reports_a_mission_with_no_tasks_yet() -> None:
    mission = _mission()
    listing = TaskListing(mission=mission, tasks=[])

    output = render_task_listing(listing)

    assert "No tasks recorded for this mission yet." in output
