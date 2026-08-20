"""Deterministic TaskGraph validation (Chapter 4.2–4.4)."""

from __future__ import annotations

from collections import defaultdict, deque

from engine.contracts.task import Task
from engine.contracts.task_graph_edge import TaskGraphEdge
from engine.contracts.validation_report import ValidationReport
from engine.planning.hashing import graph_hash, topological_task_ids

IMPLEMENTING = frozenset(
    {
        "implementation",
        "integration",
        "repair",
        "enabling",
        "specification",
        "documentation",
    }
)


def _module(path: str) -> str:
    return path.replace("\\", "/").split("/", 1)[0]


def in_scope(path: str, scope: list[str]) -> bool:
    """Chapter 4.5 rule 3: is `path` within one of the mission's declared
    `scope` prefixes? Shared by the in-memory `TaskPlanner.amend()` and the
    PostgreSQL-backed `TaskGraphService.amend_task_graph()` so both refuse a
    `widen_scope`-style escape identically."""
    normalised = path.replace("\\", "/").rstrip("/")
    for item in scope:
        prefix = item.replace("\\", "/").rstrip("/")
        if normalised == prefix or normalised.startswith(f"{prefix}/"):
            return True
    return False


def scopes_overlap(left: list[str], right: list[str]) -> bool:
    for first in left:
        for second in right:
            a = first.replace("\\", "/").rstrip("/")
            b = second.replace("\\", "/").rstrip("/")
            if a == b or a.startswith(f"{b}/") or b.startswith(f"{a}/"):
                return True
    return False


def has_cycle(tasks: list[Task], edges: list[TaskGraphEdge]) -> bool:
    return len(topological_task_ids(tasks, edges)) != len(tasks)


def validate_graph(
    tasks: list[Task],
    edges: list[TaskGraphEdge],
    *,
    expected_hash: str | None = None,
    approved_requirement_slugs: set[str] | None = None,
) -> ValidationReport:
    codes: list[str] = []
    messages: list[str] = []

    def fail(code: str, message: str) -> None:
        codes.append(code)
        messages.append(message)

    if has_cycle(tasks, edges):
        fail("GRAPH_INVALID", "TaskGraph contains a cycle")

    outgoing: dict[object, list[TaskGraphEdge]] = defaultdict(list)
    incoming: dict[object, list[TaskGraphEdge]] = defaultdict(list)
    for edge in edges:
        outgoing[edge.from_task_id].append(edge)
        incoming[edge.to_task_id].append(edge)

    for task in tasks:
        enabling_ok = task.task_class == "enabling" and task.parent_task_id is not None
        if not task.requirement_refs and not enabling_ok:
            fail("GRAPH_INVALID", f"Untraceable node {task.task_id}")
        if approved_requirement_slugs is not None:
            unknown = [
                slug
                for slug in task.requirement_refs
                if slug not in approved_requirement_slugs
            ]
            if unknown:
                fail("GRAPH_INVALID", f"Unknown requirement refs on {task.task_id}")
        if not 1 <= len(task.success_criteria) <= 5:
            fail("GRAPH_INVALID", f"Success criteria out of range on {task.task_id}")
        if task.estimated_effort == "l":
            fail(
                "DECOMPOSITION_REQUIRED", f"Effort l must be decomposed: {task.task_id}"
            )
        if task.task_class in IMPLEMENTING and not task.expected_write_scope:
            fail(
                "GRAPH_INVALID",
                f"Empty write scope on implementing node {task.task_id}",
            )
        modules = {_module(path) for path in task.expected_write_scope}
        if len(task.expected_write_scope) > 12 or len(modules) > 1:
            fail("GRAPH_INVALID", f"Write scope too large on {task.task_id}")

    terminals = [
        task
        for task in tasks
        if not any(edge.edge_type != "verifies" for edge in outgoing[task.task_id])
    ]
    for task in terminals:
        verified = any(edge.edge_type == "verifies" for edge in incoming[task.task_id])
        verifies_out = any(
            edge.edge_type == "verifies" for edge in outgoing[task.task_id]
        )
        is_verifier = task.task_class == "verification"
        if not (verified or verifies_out or is_verifier):
            fail("GRAPH_INVALID", f"Unverified terminal node {task.task_id}")

    if expected_hash is not None and graph_hash(tasks, edges) != expected_hash:
        fail("GRAPH_INVALID", "graph_hash does not match canonical topological form")

    return ValidationReport(valid=not codes, error_codes=codes, messages=messages)


def ready_predecessors_complete(
    task: Task, tasks: list[Task], edges: list[TaskGraphEdge]
) -> bool:
    by_id = {item.task_id: item for item in tasks}
    for edge in edges:
        if edge.to_task_id != task.task_id:
            continue
        if edge.edge_type == "blocks_on_decision":
            predecessor = by_id[edge.from_task_id]
            if predecessor.status != "COMPLETED":
                return False
        if edge.edge_type in {"depends_on", "produces_contract_for"}:
            predecessor = by_id[edge.from_task_id]
            if predecessor.status != "COMPLETED":
                return False
    return True


def blocked_on_decision(
    task: Task, edges: list[TaskGraphEdge], tasks: list[Task]
) -> bool:
    by_id = {item.task_id: item for item in tasks}
    for edge in edges:
        if edge.to_task_id != task.task_id or edge.edge_type != "blocks_on_decision":
            continue
        if by_id[edge.from_task_id].status != "COMPLETED":
            return True
    return False


def dependents(task_id: object, edges: list[TaskGraphEdge]) -> set[object]:
    adj: dict[object, list[object]] = defaultdict(list)
    for edge in edges:
        adj[edge.from_task_id].append(edge.to_task_id)
    seen: set[object] = set()
    queue = deque(adj[task_id])
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        queue.extend(adj[current])
    return seen
