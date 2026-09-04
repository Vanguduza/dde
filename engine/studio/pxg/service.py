"""DDE-069 Project Experience Graph service.

The PXG is the semantic model of what a project's frontend actually is.
Every other Frontend Studio subsystem addresses the frontend through a
node's `pxg_key` rather than through DOM position, so a reflow cannot
silently repoint a selection, an inspector or a provenance record at a
different component.

Revision semantics. `pxg_revision` is a project-wide monotonic counter.
Each write bumps it once and stamps every row it touched, so the current
revision is `max(pxg_revision)` across the project's nodes and edges. A
mutation precondition carrying an older revision is stale and is refused
rather than blindly applied (FRONTEND_STUDIO_REV3 section 15.1).

This service is the sole writer of `pxg_nodes` and `pxg_edges`.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from engine.contracts.pxg_edge import PxgEdge
from engine.contracts.pxg_node import PxgNode, SourceRef
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.studio.tables import pxg_edges, pxg_nodes
from engine.truth.db import open_unit_of_work

# A key is a path of dot/dash/alnum segments, optionally addressing a
# region or component within a screen after '#'. Keys are compared
# literally everywhere, so the grammar is enforced on write rather than
# left to each caller's discretion.
PXG_KEY_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*"
    r"(#[A-Za-z0-9][A-Za-z0-9._-]*)?$"
)

MAX_KEY_LENGTH = 512


@dataclass(frozen=True)
class NodeInput:
    """A node to upsert. `pxg_key` is the identity; node_id is derived."""

    pxg_key: str
    node_kind: str
    title: str
    parent_key: str | None = None
    source_refs: tuple[SourceRef, ...] = ()
    attributes: dict[str, object] | None = None
    provenance: dict[str, object] | None = None


@dataclass(frozen=True)
class EdgeInput:
    from_key: str
    to_key: str
    edge_kind: str
    attributes: dict[str, object] | None = None


@dataclass(frozen=True)
class PxgGraph:
    """A project's graph at one revision, with reconciliation findings."""

    revision: int
    nodes: tuple[PxgNode, ...]
    edges: tuple[PxgEdge, ...]

    def node_by_key(self, key: str) -> PxgNode | None:
        for node in self.nodes:
            if node.pxg_key == key:
                return node
        return None

    def children_of(self, key: str | None) -> tuple[PxgNode, ...]:
        return tuple(node for node in self.nodes if node.parent_key == key)

    def nodes_of_kind(self, kind: str) -> tuple[PxgNode, ...]:
        return tuple(node for node in self.nodes if node.node_kind == kind)

    def dangling_edges(self) -> tuple[PxgEdge, ...]:
        keys = {node.pxg_key for node in self.nodes}
        return tuple(
            edge
            for edge in self.edges
            if edge.from_key not in keys or edge.to_key not in keys
        )

    def orphan_nodes(self) -> tuple[PxgNode, ...]:
        """Nodes naming a parent that does not exist. Distinct from a
        root node, whose parent_key is legitimately null."""
        keys = {node.pxg_key for node in self.nodes}
        return tuple(
            node
            for node in self.nodes
            if node.parent_key is not None and node.parent_key not in keys
        )


def validate_key(key: str) -> str:
    if not key or len(key) > MAX_KEY_LENGTH or not PXG_KEY_RE.match(key):
        raise DdeError(
            "VALIDATION_FAILED",
            "pxg_key must be slash-separated segments with an optional "
            "'#fragment', and at most 512 characters",
            retryable=False,
            details={"pxg_key": key[:200]},
        )
    return key


class PxgService:
    """Reads and writes the Project Experience Graph."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def current_revision(self, *, tenant_id: UUID, project_id: UUID) -> int:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            return await self._current_revision(
                uow.connection, tenant_id=tenant_id, project_id=project_id
            )

    async def _current_revision(
        self, connection: AsyncConnection, *, tenant_id: UUID, project_id: UUID
    ) -> int:
        node_max = await connection.scalar(
            select(func.max(pxg_nodes.c.pxg_revision)).where(
                pxg_nodes.c.tenant_id == tenant_id,
                pxg_nodes.c.project_id == project_id,
            )
        )
        edge_max = await connection.scalar(
            select(func.max(pxg_edges.c.pxg_revision)).where(
                pxg_edges.c.tenant_id == tenant_id,
                pxg_edges.c.project_id == project_id,
            )
        )
        return max(int(node_max or 0), int(edge_max or 0))

    async def load(self, *, tenant_id: UUID, project_id: UUID) -> PxgGraph:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            nodes = await self._load_nodes(
                uow.connection, tenant_id=tenant_id, project_id=project_id
            )
            edges = await self._load_edges(
                uow.connection, tenant_id=tenant_id, project_id=project_id
            )
            revision = await self._current_revision(
                uow.connection, tenant_id=tenant_id, project_id=project_id
            )
        return PxgGraph(revision=revision, nodes=nodes, edges=edges)

    async def _load_nodes(
        self, connection: AsyncConnection, *, tenant_id: UUID, project_id: UUID
    ) -> tuple[PxgNode, ...]:
        result = await connection.execute(
            select(pxg_nodes)
            .where(
                pxg_nodes.c.tenant_id == tenant_id,
                pxg_nodes.c.project_id == project_id,
            )
            .order_by(pxg_nodes.c.pxg_key)
        )
        return tuple(
            PxgNode.model_validate(dict(row)) for row in result.mappings().all()
        )

    async def _load_edges(
        self, connection: AsyncConnection, *, tenant_id: UUID, project_id: UUID
    ) -> tuple[PxgEdge, ...]:
        result = await connection.execute(
            select(pxg_edges)
            .where(
                pxg_edges.c.tenant_id == tenant_id,
                pxg_edges.c.project_id == project_id,
            )
            .order_by(pxg_edges.c.from_key, pxg_edges.c.edge_kind, pxg_edges.c.to_key)
        )
        return tuple(
            PxgEdge.model_validate(dict(row)) for row in result.mappings().all()
        )

    async def apply(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        nodes: Sequence[NodeInput] = (),
        edges: Sequence[EdgeInput] = (),
        remove_node_keys: Sequence[str] = (),
    ) -> int:
        """Upsert nodes/edges at one new revision; return that revision.

        A single call is one revision, so a caller cannot half-apply a
        graph change and leave readers observing a torn state.
        """
        if not nodes and not edges and not remove_node_keys:
            raise DdeError(
                "VALIDATION_FAILED",
                "an empty PXG write would consume a revision for nothing",
                retryable=False,
            )
        for node in nodes:
            validate_key(node.pxg_key)
            if node.parent_key is not None:
                validate_key(node.parent_key)
            if node.parent_key == node.pxg_key:
                raise DdeError(
                    "VALIDATION_FAILED",
                    "a PXG node cannot be its own parent",
                    retryable=False,
                    details={"pxg_key": node.pxg_key},
                )
        for edge in edges:
            validate_key(edge.from_key)
            validate_key(edge.to_key)

        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            connection = uow.connection
            revision = (
                await self._current_revision(
                    connection, tenant_id=tenant_id, project_id=project_id
                )
                + 1
            )
            for node in nodes:
                await connection.execute(
                    pg_insert(pxg_nodes)
                    .values(
                        node_id=uuid7(),
                        tenant_id=tenant_id,
                        project_id=project_id,
                        pxg_key=node.pxg_key,
                        node_kind=node.node_kind,
                        title=node.title,
                        parent_key=node.parent_key,
                        pxg_revision=revision,
                        source_refs=[
                            ref.model_dump(mode="json", exclude_none=True)
                            for ref in node.source_refs
                        ],
                        attributes=node.attributes or {},
                        provenance=node.provenance or {},
                        lock_version=1,
                        created_at=now,
                        updated_at=now,
                    )
                    .on_conflict_do_update(
                        index_elements=["tenant_id", "project_id", "pxg_key"],
                        set_={
                            "node_kind": node.node_kind,
                            "title": node.title,
                            "parent_key": node.parent_key,
                            "pxg_revision": revision,
                            "source_refs": [
                                ref.model_dump(mode="json", exclude_none=True)
                                for ref in node.source_refs
                            ],
                            "attributes": node.attributes or {},
                            "provenance": node.provenance or {},
                            "lock_version": pxg_nodes.c.lock_version + 1,
                            "updated_at": now,
                        },
                    )
                )
            for edge in edges:
                await connection.execute(
                    pg_insert(pxg_edges)
                    .values(
                        edge_id=uuid7(),
                        tenant_id=tenant_id,
                        project_id=project_id,
                        from_key=edge.from_key,
                        to_key=edge.to_key,
                        edge_kind=edge.edge_kind,
                        pxg_revision=revision,
                        attributes=edge.attributes or {},
                        created_at=now,
                        updated_at=now,
                    )
                    .on_conflict_do_update(
                        index_elements=[
                            "tenant_id",
                            "project_id",
                            "from_key",
                            "edge_kind",
                            "to_key",
                        ],
                        set_={
                            "pxg_revision": revision,
                            "attributes": edge.attributes or {},
                            "updated_at": now,
                        },
                    )
                )
            for key in remove_node_keys:
                await connection.execute(
                    delete(pxg_nodes).where(
                        pxg_nodes.c.tenant_id == tenant_id,
                        pxg_nodes.c.project_id == project_id,
                        pxg_nodes.c.pxg_key == key,
                    )
                )
            await uow.commit()
        return revision
