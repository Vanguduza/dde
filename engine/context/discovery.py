"""Chapter 5.1 Discovery: resolve a Task's explicit refs before retrieval.

Discovery only resolves `expected_read_scope` against the repository
working tree (Chapter 5.2's "Explicit reference" retriever definition:
"Direct fetch by ID/path"). Requirement/feature refs are identity strings
resolved later, by the authority retriever, against Project Truth.
"""

from __future__ import annotations

from pathlib import Path

from engine.context.model import DiscoveryResult
from engine.contracts.task import Task


def discover(task: Task, *, root: Path) -> DiscoveryResult:
    resolved: list[str] = []
    unresolved: list[str] = []
    for entry in task.expected_read_scope:
        candidate = (root / entry).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            # Refuses to resolve a scope entry that escapes the repo root
            # (e.g. `../secrets`) rather than silently following it.
            unresolved.append(entry)
            continue
        if candidate.exists():
            resolved.append(entry)
        else:
            unresolved.append(entry)
    return DiscoveryResult(
        requirement_refs=tuple(task.requirement_refs),
        feature_refs=tuple(task.feature_refs),
        expected_read_scope=tuple(task.expected_read_scope),
        expected_write_scope=tuple(task.expected_write_scope),
        resolved_paths=tuple(resolved),
        unresolved_paths=tuple(unresolved),
    )
