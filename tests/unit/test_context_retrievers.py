"""Chapter 5.2 Stage 1 retrievers, tested independently against a small,
fully-controlled synthetic working tree (not this live repository)."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from engine.context.discovery import discover
from engine.context.retrievers import explicit, lexical, structural
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
        title="Compute totals",
        intent="Verify calculate_total sums invoice items correctly",
        task_class="verification",
        requirement_refs=[],
        feature_refs=[],
        success_criteria=["calculate_total returns the correct sum"],
        expected_write_scope=["pkg"],
        expected_read_scope=["pkg/mod.py"],
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


def _build_repo(root: Path) -> None:
    (root / "pkg").mkdir()
    (root / "pkg" / "mod.py").write_text(
        "def calculate_total(items):\n"
        "    return sum(items)\n"
        "\n"
        "\n"
        "class Invoice:\n"
        "    def total(self):\n"
        "        return calculate_total(self.items)\n",
        encoding="utf-8",
    )
    (root / "AGENTS.md").write_text(
        "Never pass a long-lived credential. RLS enforces tenant isolation.\n",
        encoding="utf-8",
    )


def test_explicit_retriever_reads_declared_paths(tmp_path: Path) -> None:
    _build_repo(tmp_path)
    task = _task()
    discovery = discover(task, root=tmp_path)

    items = explicit.retrieve(
        discovery, root=tmp_path, expected_write_scope=task.expected_write_scope
    )

    assert len(items) == 1
    assert items[0].key == "file:pkg/mod.py"
    assert "calculate_total" in items[0].content
    assert items[0].write_scope_match is True
    assert items[0].categories == ("impacted_code_and_deps",)


def test_explicit_retriever_skips_unresolved_paths(tmp_path: Path) -> None:
    _build_repo(tmp_path)
    task = _task(expected_read_scope=["pkg/mod.py", "does_not_exist.py"])
    discovery = discover(task, root=tmp_path)

    items = explicit.retrieve(
        discovery, root=tmp_path, expected_write_scope=task.expected_write_scope
    )

    assert [item.source_path for item in items] == ["pkg/mod.py"]


def test_lexical_retriever_stdlib_fallback_finds_matching_file(tmp_path: Path) -> None:
    _build_repo(tmp_path)
    task = _task()

    items = lexical.retrieve(
        task,
        root=tmp_path,
        expected_write_scope=task.expected_write_scope,
        use_ripgrep=False,
    )

    assert any(item.source_path == "pkg/mod.py" for item in items)
    matched = next(item for item in items if item.source_path == "pkg/mod.py")
    assert "calculate_total" in matched.content
    assert matched.write_scope_match is True


@pytest.mark.skipif(
    shutil.which("rg") is None,
    reason="requires a real `rg` (ripgrep) binary resolvable on PATH; this "
    "test forces the ripgrep code path (use_ripgrep=True) and cannot "
    "distinguish 'no rg' from 'rg disagrees with stdlib' otherwise",
)
def test_lexical_retriever_ripgrep_and_stdlib_agree_on_files_found(
    tmp_path: Path,
) -> None:
    """Chapter 5.2's ripgrep path and the stdlib fallback are two
    implementations of the same contract — the file set they surface
    must match even if internal scoring/formatting differs."""
    _build_repo(tmp_path)
    task = _task()

    stdlib_items = lexical.retrieve(
        task,
        root=tmp_path,
        expected_write_scope=task.expected_write_scope,
        use_ripgrep=False,
    )
    ripgrep_items = lexical.retrieve(
        task,
        root=tmp_path,
        expected_write_scope=task.expected_write_scope,
        use_ripgrep=True,
    )

    assert {item.source_path for item in stdlib_items} == {
        item.source_path for item in ripgrep_items
    }


def test_lexical_retriever_tags_agents_md_as_architecture_and_security(
    tmp_path: Path,
) -> None:
    _build_repo(tmp_path)
    task = _task(
        title="Review credential handling",
        intent="Confirm RLS and tenant isolation for credential access",
        success_criteria=["No credential leaks past RLS"],
        expected_read_scope=[],
        expected_write_scope=["docs"],
    )

    items = lexical.retrieve(
        task,
        root=tmp_path,
        expected_write_scope=task.expected_write_scope,
        use_ripgrep=False,
    )

    agents_item = next(item for item in items if item.source_path == "AGENTS.md")
    assert "architecture_constraints" in agents_item.categories
    assert "security_constraints" in agents_item.categories


def test_structural_retriever_finds_matching_definition(tmp_path: Path) -> None:
    _build_repo(tmp_path)
    task = _task()
    discovery = discover(task, root=tmp_path)

    items = structural.retrieve(
        task, discovery, root=tmp_path, expected_write_scope=task.expected_write_scope
    )

    keys = {item.key for item in items}
    assert "symbol:pkg/mod.py::calculate_total" in keys
    matched = next(
        item for item in items if item.key == "symbol:pkg/mod.py::calculate_total"
    )
    assert "def calculate_total" in matched.content
    assert matched.write_scope_match is True


def test_structural_retriever_returns_nothing_when_no_terms_match(
    tmp_path: Path,
) -> None:
    _build_repo(tmp_path)
    task = _task(
        title="Unrelated",
        intent="zzzznonexistentqqq widget frobnication",
        success_criteria=["Nothing to see here"],
    )
    discovery = discover(task, root=tmp_path)

    items = structural.retrieve(
        task, discovery, root=tmp_path, expected_write_scope=task.expected_write_scope
    )

    assert items == []
