"""Canonical TaskGraph hashing (Chapter 4.2)."""

from __future__ import annotations

from collections import defaultdict, deque

from engine.contracts.task import Task
from engine.contracts.task_graph_edge import TaskGraphEdge
from engine.core.hashing import canonical_json, sha256_hex

DEPENDENCY_EDGES = frozenset(
    {"depends_on", "produces_contract_for", "blocks_on_decision", "repairs"}
)


def topological_task_ids(tasks: list[Task], edges: list[TaskGraphEdge]) -> list[str]:
    ids = sorted(str(task.task_id) for task in tasks)
    incoming: dict[str, int] = {task_id: 0 for task_id in ids}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        if edge.edge_type not in DEPENDENCY_EDGES:
            continue
        source = str(edge.from_task_id)
        dest = str(edge.to_task_id)
        outgoing[source].append(dest)
        incoming[dest] = incoming.get(dest, 0) + 1
        incoming.setdefault(source, incoming.get(source, 0))
    ready = deque(sorted(task_id for task_id, count in incoming.items() if count == 0))
    ordered: list[str] = []
    while ready:
        current = ready.popleft()
        ordered.append(current)
        for dest in sorted(outgoing[current]):
            incoming[dest] -= 1
            if incoming[dest] == 0:
                ready.append(dest)
        ready = deque(sorted(ready))
    return ordered


def graph_hash(tasks: list[Task], edges: list[TaskGraphEdge]) -> str:
    order = topological_task_ids(tasks, edges)
    by_id = {str(task.task_id): task for task in tasks}
    nodes = []
    for task_id in order if len(order) == len(tasks) else sorted(by_id):
        task = by_id[task_id]
        nodes.append(
            {
                "task_id": task_id,
                "title": task.title,
                "intent": task.intent,
                "task_class": task.task_class,
                "requirement_refs": sorted(task.requirement_refs),
                "feature_refs": sorted(task.feature_refs),
                "success_criteria": task.success_criteria,
                "expected_write_scope": sorted(task.expected_write_scope),
                "expected_read_scope": sorted(task.expected_read_scope),
                "blast_radius": task.blast_radius,
                "risk_class": task.risk_class,
                "estimated_effort": task.estimated_effort,
                "autonomy_ceiling": task.autonomy_ceiling,
                "requires_approval": task.requires_approval,
                "parent_task_id": (
                    None if task.parent_task_id is None else str(task.parent_task_id)
                ),
                "verification_profile_ref": task.verification_profile_ref,
            }
        )
    edge_items = sorted(
        (
            {
                "from_task_id": str(edge.from_task_id),
                "to_task_id": str(edge.to_task_id),
                "edge_type": edge.edge_type,
                "contract_ref": edge.contract_ref,
            }
            for edge in edges
        ),
        key=lambda item: (
            item["from_task_id"],
            item["to_task_id"],
            item["edge_type"],
            item["contract_ref"] or "",
        ),
    )
    return sha256_hex(canonical_json({"nodes": nodes, "edges": edge_items}))
