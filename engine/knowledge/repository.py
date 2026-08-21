"""Async repositories for the Chapter 5.10 knowledge graph (Chapter 3.3, 3.8).

Every read and write here executes on the connection of an already-open
unit of work (Chapter 3.5); this module never begins or ends a
transaction itself.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.asserted_edge import AssertedEdge
from engine.contracts.derived_edge import DerivedEdge
from engine.knowledge.model import GraphStaleness
from engine.knowledge.tables import asserted_edges, derived_edges


class AssertedEdgeRepository:
    """Reads and writes `asserted_edges` -- the Chapter 5.10 durable,
    versioned traceability record, owned by `engine.knowledge`."""

    async def get_by_identity(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        edge_type: str,
        source_key: str,
        target_key: str,
    ) -> AssertedEdge | None:
        result = await connection.execute(
            select(asserted_edges).where(
                asserted_edges.c.project_id == project_id,
                asserted_edges.c.edge_type == edge_type,
                asserted_edges.c.source_key == source_key,
                asserted_edges.c.target_key == target_key,
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return AssertedEdge.model_validate(dict(row))

    async def insert_edge(
        self, connection: AsyncConnection, record: AssertedEdge
    ) -> None:
        await connection.execute(asserted_edges.insert().values(**record.model_dump()))

    async def retract(
        self, connection: AsyncConnection, edge_id: UUID, *, retracted_at: object
    ) -> int:
        result = await connection.execute(
            asserted_edges.update()
            .where(asserted_edges.c.edge_id == edge_id)
            .values(
                status="retracted", retracted_at=retracted_at, updated_at=retracted_at
            )
        )
        return int(result.rowcount)

    async def list_for_project(
        self, connection: AsyncConnection, project_id: UUID
    ) -> list[AssertedEdge]:
        result = await connection.execute(
            select(asserted_edges)
            .where(asserted_edges.c.project_id == project_id)
            .order_by(asserted_edges.c.created_at.asc())
        )
        return [
            AssertedEdge.model_validate(dict(row)) for row in result.mappings().all()
        ]


class DerivedEdgeRepository:
    """Reads and writes `derived_edges` -- the Chapter 5.10 disposable,
    recomputed-per-commit record, owned by `engine.knowledge`."""

    async def replace_for_project(
        self, connection: AsyncConnection, project_id: UUID, records: list[DerivedEdge]
    ) -> None:
        """Chapter 5.10: "Recomputed per integrated commit, disposable,
        never versioned." A recompute replaces the entire prior generation
        for this project in the same transaction the new rows are
        inserted in -- there is never a mix of two commits' derived edges
        for one project."""
        await connection.execute(
            delete(derived_edges).where(derived_edges.c.project_id == project_id)
        )
        if records:
            await connection.execute(
                derived_edges.insert(),
                [record.model_dump() for record in records],
            )

    async def list_for_project(
        self, connection: AsyncConnection, project_id: UUID
    ) -> list[DerivedEdge]:
        result = await connection.execute(
            select(derived_edges)
            .where(derived_edges.c.project_id == project_id)
            .order_by(derived_edges.c.created_at.asc())
        )
        return [
            DerivedEdge.model_validate(dict(row)) for row in result.mappings().all()
        ]

    async def staleness(
        self, connection: AsyncConnection, project_id: UUID, *, head_commit: str
    ) -> GraphStaleness:
        """Chapter 5.10: "Graph staleness (share of derived edges older
        than the head commit) is a monitored metric" -- computed directly
        against the persisted generation, not re-derived in Python."""
        total_result = await connection.execute(
            select(func.count())
            .select_from(derived_edges)
            .where(derived_edges.c.project_id == project_id)
        )
        total = int(total_result.scalar_one())
        stale_result = await connection.execute(
            select(func.count())
            .select_from(derived_edges)
            .where(
                derived_edges.c.project_id == project_id,
                derived_edges.c.derived_from_commit != head_commit,
            )
        )
        stale = int(stale_result.scalar_one())
        return GraphStaleness(
            head_commit=head_commit, total_count=total, stale_count=stale
        )
