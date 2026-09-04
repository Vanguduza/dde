"""DDE-069 candidate graph projection.

The accepted Project Experience Graph is never written by candidate
editing. A candidate's changes live entirely in its append-only mutation
log, and its *effective* graph is the accepted graph with those mutations
replayed over it. Promotion is the only thing that applies them to the
accepted graph.

This is what makes the isolation real rather than asserted. There is no
code path by which editing a candidate touches accepted state, because
the executor does not write nodes at all -- so "the accepted frontend
remains protected" is a property of the architecture instead of a rule
somebody has to remember.

It also makes three other things fall out for free: a candidate's change
count is the length of its applied log, staleness is a comparison of two
integers rather than a diff, and rebasing is replaying the same log over
a newer accepted graph.
"""

from __future__ import annotations

from collections.abc import Sequence

from engine.contracts.frontend_mutation import FrontendMutation
from engine.contracts.pxg_node import PxgNode
from engine.studio.pxg.service import PxgGraph


def project(accepted: PxgGraph, mutations: Sequence[FrontendMutation]) -> PxgGraph:
    """Return the candidate's effective graph.

    Only `APPLIED` mutations are replayed: `REFUSED` never happened and
    `REVERTED` has already been compensated by a later applied row, so
    replaying it would undo the compensation.
    """
    nodes: dict[str, PxgNode] = {node.pxg_key: node for node in accepted.nodes}
    revision = accepted.revision

    for mutation in sorted(mutations, key=lambda item: item.sequence):
        if mutation.status != "APPLIED":
            continue
        revision += 1
        if mutation.operation == "REMOVE":
            nodes.pop(mutation.target_key, None)
            continue
        nodes[mutation.target_key] = _apply(
            nodes.get(mutation.target_key), mutation, revision
        )

    return PxgGraph(
        revision=revision,
        nodes=tuple(sorted(nodes.values(), key=lambda node: node.pxg_key)),
        edges=accepted.edges,
    )


def _apply(
    existing: PxgNode | None, mutation: FrontendMutation, revision: int
) -> PxgNode:
    payload = dict(mutation.payload)
    attributes = dict(existing.attributes) if existing else {}
    prop = payload.get("property")
    if isinstance(prop, str):
        attributes[prop] = payload.get("value")

    requested_parent = payload.get("parent_key")
    parent_key = (
        requested_parent
        if isinstance(requested_parent, str) and requested_parent
        else (existing.parent_key if existing else None)
    )

    if existing is not None:
        return existing.model_copy(
            update={
                "title": str(payload.get("title") or existing.title),
                "parent_key": parent_key,
                "attributes": attributes,
                "pxg_revision": revision,
                "lock_version": existing.lock_version + 1,
                "updated_at": mutation.updated_at,
            }
        )

    # An ADD onto a key with no accepted node: the candidate introduces
    # it. It carries the mutation's identity so provenance survives
    # promotion.
    return PxgNode(
        node_id=mutation.mutation_id,
        tenant_id=mutation.tenant_id,
        project_id=mutation.project_id,
        pxg_key=mutation.target_key,
        node_kind=str(payload.get("node_kind") or "component"),
        title=str(payload.get("title") or mutation.target_key),
        parent_key=parent_key,
        pxg_revision=revision,
        source_refs=[],
        attributes=attributes,
        provenance={"introduced_by_mutation_id": str(mutation.mutation_id)},
        lock_version=1,
        created_at=mutation.created_at,
        updated_at=mutation.updated_at,
    )


def change_count(mutations: Sequence[FrontendMutation]) -> int:
    """The candidate strip's "N changes" -- a real count of applied
    structural changes, not a placeholder."""
    return sum(1 for item in mutations if item.status == "APPLIED")
