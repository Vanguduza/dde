"""Chapter 5.1 Discovery: resolving a Task's `expected_read_scope` against
a working tree."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from engine.context.discovery import discover
from engine.contracts.task import Task
from engine.core.ids import uuid7


def _task(**overrides: object) -> Task:
    now = datetime.now(UTC)
    defaults: dict[str, object] = dict(
        task_id=uuid7(),
        tenant_id=uuid7(),
        project_id=uuid7(),
        mission_id=uuid7(),
        graph_id=uuid7(),
        title="t",
        intent="i",
        task_class="verification",
        requirement_refs=["REQ-1"],
        feature_refs=[],
        success_criteria=["c"],
        expected_write_scope=["pkg"],
        expected_read_scope=["pkg/mod.py", "missing.py"],
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
    defaults.update(overrides)
    return Task.model_validate(defaults)


def test_discover_resolves_existing_paths_and_flags_missing_ones(
    tmp_path: Path,
) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text("x = 1\n", encoding="utf-8")

    result = discover(_task(), root=tmp_path)

    assert result.resolved_paths == ("pkg/mod.py",)
    assert result.unresolved_paths == ("missing.py",)
    assert result.requirement_refs == ("REQ-1",)
    assert result.expected_write_scope == ("pkg",)


def test_discover_refuses_paths_that_escape_the_repo_root(tmp_path: Path) -> None:
    task = _task(expected_read_scope=["../outside.py"])

    result = discover(task, root=tmp_path)

    assert result.resolved_paths == ()
    assert result.unresolved_paths == ("../outside.py",)
