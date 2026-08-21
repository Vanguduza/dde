"""Production Chapter 5.10 knowledge graph -- the sole writer of
`asserted_edges` and `derived_edges` rows in PostgreSQL (Chapter 2.6, 3.5,
3.8).

``assert_edge`` is the durable, versioned half: idempotent on
``(project_id, edge_type, source_key, target_key)`` -- a caller that
re-asserts the same edge (e.g. re-approving an already-approved TaskGraph
in a retry) gets back the existing row rather than a duplicate insert or
an error (AGENTS.md: "Retrying a side-effecting operation without an
idempotency key" is forbidden; the unique constraint on that tuple is the
idempotency key here). ``retract_edge`` moves a row from ``active`` to
``retracted`` without a physical delete -- Chapter 5.10: asserted edges
are "durable, versioned".

``recompute_derived_edges`` is the disposable half: it replaces a
project's entire prior generation of `derived_edges` with a freshly
computed one from `engine.knowledge.deriver` inside one transaction, and
reports the resulting `GraphStaleness` (Chapter 5.10's monitored metric).

**Flagged Stage 1 divergence.** Chapter 5.10 ties the derived-edge
recompute to "per integrated commit" -- i.e. the Chapter 10 integration/
merge queue (`engine.integration`) landing a commit. This mission wires
`assert_edge` into a real production mutation call site
(`engine.missions.service.MissionService.create_task_graph`, asserting
`task_to_requirement` edges when a TaskGraph reaches `APPROVED`) but does
**not** wire `recompute_derived_edges` into `engine.integration`'s merge
path -- that is a real, working, independently-tested service method a
future mission should call from the merge queue once a commit lands,
not a silently-dropped requirement. Recording this here rather than
leaving it to be discovered later follows the same disclosure discipline
`engine.context.conflict`/`engine.context.critic` (DDE-031) used for
their own Stage 1 gaps.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.context.repo import current_commit_sha, repo_root
from engine.contracts.asserted_edge import AssertedEdge
from engine.contracts.derived_edge import DerivedEdge
from engine.core.clock import Clock, SystemClock
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.knowledge.deriver import DERIVER_VERSION, derive_all
from engine.knowledge.model import GraphStaleness
from engine.knowledge.repository import AssertedEdgeRepository, DerivedEdgeRepository
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")


class KnowledgeGraphService:
    """Async, PostgreSQL-backed writer for `asserted_edges`/`derived_edges`
    (Chapter 3.8). Each public method opens and commits its own unit of
    work unless one is supplied, so a caller composing a cross-module
    transaction (Chapter 3.5) can share it instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        events: EventService | None = None,
        asserted_repository: AssertedEdgeRepository | None = None,
        derived_repository: DerivedEdgeRepository | None = None,
        clock: Clock | None = None,
        root: Path | None = None,
    ) -> None:
        self._engine = engine
        self._events = events or EventService(engine)
        self._asserted = asserted_repository or AssertedEdgeRepository()
        self._derived = derived_repository or DerivedEdgeRepository()
        self._clock = clock or SystemClock()
        self._root = root or repo_root()

    async def _run(
        self,
        uow: PostgresUnitOfWork | None,
        tenant_id: UUID,
        project_id: UUID,
        body: Callable[[PostgresUnitOfWork], Awaitable[T]],
    ) -> T:
        if uow is not None:
            return await body(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as owned:
            result = await body(owned)
            await owned.commit()
            return result

    async def assert_edge(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        edge_type: str,
        source_key: str,
        target_key: str,
        asserted_by_mechanism: str,
        asserted_by_principal: UUID | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> AssertedEdge:
        """Chapter 5.10: write (or idempotently return) one durable
        asserted edge."""

        async def _op(active: PostgresUnitOfWork) -> AssertedEdge:
            existing = await self._asserted.get_by_identity(
                active.connection,
                project_id=project_id,
                edge_type=edge_type,
                source_key=source_key,
                target_key=target_key,
            )
            if existing is not None:
                return existing
            now = self._clock.now()
            edge = AssertedEdge(
                edge_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                edge_type=edge_type,
                source_key=source_key,
                target_key=target_key,
                asserted_by_principal=asserted_by_principal,
                asserted_by_mechanism=asserted_by_mechanism,
                status="active",
                retracted_at=None,
                created_at=now,
                updated_at=now,
            )
            await self._asserted.insert_edge(active.connection, edge)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="KnowledgeGraphEdgeAsserted",
                aggregate_type="asserted_edge",
                aggregate_id=edge.edge_id,
                payload={
                    "edge_type": edge_type,
                    "source_key": source_key,
                    "target_key": target_key,
                    "asserted_by_mechanism": asserted_by_mechanism,
                },
                uow=active,
            )
            return edge

        return await self._run(uow, tenant_id, project_id, _op)

    async def retract_edge(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        edge_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> None:
        async def _op(active: PostgresUnitOfWork) -> None:
            now = self._clock.now()
            await self._asserted.retract(active.connection, edge_id, retracted_at=now)

        await self._run(uow, tenant_id, project_id, _op)

    async def recompute_derived_edges(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> GraphStaleness:
        """Chapter 5.10: replace this project's entire derived-edge
        generation with a fresh structural recompute over the current
        working tree, stamped with the current commit, and report the
        resulting staleness (trivially `0.0` immediately after a
        recompute -- every row's `derived_from_commit` is the commit just
        read)."""

        async def _op(active: PostgresUnitOfWork) -> GraphStaleness:
            head_commit = current_commit_sha(self._root)
            now = self._clock.now()
            candidates = derive_all(self._root)
            records = [
                DerivedEdge(
                    derived_edge_id=uuid7(),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    edge_type=candidate.edge_type,
                    source_key=candidate.source_key,
                    target_key=candidate.target_key,
                    derived_at=now,
                    derived_from_commit=head_commit,
                    deriver_version=DERIVER_VERSION,
                    created_at=now,
                    updated_at=now,
                )
                for candidate in candidates
            ]
            await self._derived.replace_for_project(
                active.connection, project_id, records
            )
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="KnowledgeGraphRecomputed",
                aggregate_type="derived_edge",
                aggregate_id=uuid7(),
                payload={
                    "edge_count": len(records),
                    "head_commit": head_commit,
                    "deriver_version": DERIVER_VERSION,
                },
                uow=active,
            )
            return GraphStaleness(
                head_commit=head_commit,
                total_count=len(records),
                stale_count=0,
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def staleness(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> GraphStaleness:
        async def _op(active: PostgresUnitOfWork) -> GraphStaleness:
            head_commit = current_commit_sha(self._root)
            return await self._derived.staleness(
                active.connection, project_id, head_commit=head_commit
            )

        return await self._run(uow, tenant_id, project_id, _op)
