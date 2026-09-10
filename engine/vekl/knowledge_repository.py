"""Project-scoped persistence for the Production VEKL knowledge topology.

All rows are projections/evidence. Existing truth/task/source/verification
services remain owners of their authoritative objects.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.vekl_conflict_observation import VEKLConflictObservation
from engine.contracts.vekl_execution_knowledge_binding import (
    VEKLExecutionKnowledgeBinding,
)
from engine.contracts.vekl_graph_invalidation import VEKLGraphInvalidation
from engine.contracts.vekl_knowledge_edge import VEKLKnowledgeEdge
from engine.contracts.vekl_knowledge_node import VEKLKnowledgeNode
from engine.contracts.vekl_research_finding import VEKLResearchFinding
from engine.contracts.vekl_resolution_trace import VEKLResolutionTrace
from engine.contracts.vekl_retrieval_route import VEKLRetrievalRoute
from engine.contracts.vekl_truth_challenge import VEKLTruthChallenge
from engine.contracts.vekl_truth_challenge_finding import VEKLTruthChallengeFinding
from engine.contracts.vekl_unit_map import VEKLUnitMap
from engine.core.hashing import canonical_json, sha256_hex
from engine.vekl.tables import (
    vekl_conflict_observations,
    vekl_execution_knowledge_bindings,
    vekl_graph_invalidations,
    vekl_knowledge_edges,
    vekl_knowledge_nodes,
    vekl_research_findings,
    vekl_resolution_traces,
    vekl_retrieval_routes,
    vekl_truth_challenge_findings,
    vekl_truth_challenges,
    vekl_unit_maps,
)


def _unit_map_hash(record: VEKLUnitMap, **changes: object) -> str:
    payload = record.model_dump(mode="json")
    payload.update(changes)
    for key in ("unit_map_hash", "created_at", "updated_at", "invalidated_at"):
        payload.pop(key, None)
    return sha256_hex(canonical_json(payload))


class VEKLKnowledgeRepository:
    async def insert_unit_map(
        self, connection: AsyncConnection, record: VEKLUnitMap
    ) -> None:
        await connection.execute(vekl_unit_maps.insert().values(**record.model_dump()))

    async def unit_map_by_revision(
        self, connection: AsyncConnection, *, project_id: UUID, unit_revision_hash: str
    ) -> VEKLUnitMap | None:
        result = await connection.execute(
            select(vekl_unit_maps).where(
                vekl_unit_maps.c.project_id == project_id,
                vekl_unit_maps.c.unit_revision_hash == unit_revision_hash,
            )
        )
        row = result.mappings().first()
        return None if row is None else VEKLUnitMap.model_validate(dict(row))

    async def get_unit_map(
        self, connection: AsyncConnection, *, project_id: UUID, unit_map_id: UUID
    ) -> VEKLUnitMap | None:
        result = await connection.execute(
            select(vekl_unit_maps).where(
                vekl_unit_maps.c.project_id == project_id,
                vekl_unit_maps.c.unit_map_id == unit_map_id,
            )
        )
        row = result.mappings().first()
        return None if row is None else VEKLUnitMap.model_validate(dict(row))

    async def list_active_unit_maps(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        task_graph_id: UUID | None = None,
    ) -> list[VEKLUnitMap]:
        query = select(vekl_unit_maps).where(
            vekl_unit_maps.c.project_id == project_id,
            vekl_unit_maps.c.invalidated_at.is_(None),
        )
        if task_graph_id is not None:
            query = query.where(vekl_unit_maps.c.task_graph_id == task_graph_id)
        result = await connection.execute(
            query.order_by(vekl_unit_maps.c.created_at, vekl_unit_maps.c.unit_map_id)
        )
        return [VEKLUnitMap.model_validate(dict(row)) for row in result.mappings()]

    async def active_unit_maps_by_lineage(
        self, connection: AsyncConnection, *, project_id: UUID, unit_lineage_id: str
    ) -> list[VEKLUnitMap]:
        result = await connection.execute(
            select(vekl_unit_maps).where(
                vekl_unit_maps.c.project_id == project_id,
                vekl_unit_maps.c.unit_lineage_id == unit_lineage_id,
                vekl_unit_maps.c.invalidated_at.is_(None),
            )
        )
        return [VEKLUnitMap.model_validate(dict(row)) for row in result.mappings()]

    async def invalidate_unit_map(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        unit_map_id: UUID,
        reason: str,
        invalidated_at: datetime,
    ) -> None:
        current = await self.get_unit_map(
            connection, project_id=project_id, unit_map_id=unit_map_id
        )
        if current is None:
            return
        reasons = list(current.invalidation_reasons)
        if reason not in reasons:
            reasons.append(reason)
        next_hash = _unit_map_hash(
            current,
            invalidation_reasons=reasons,
            knowledge_readiness_state="STALE",
        )
        await connection.execute(
            update(vekl_unit_maps)
            .where(
                vekl_unit_maps.c.project_id == project_id,
                vekl_unit_maps.c.unit_map_id == unit_map_id,
            )
            .values(
                invalidated_at=invalidated_at,
                updated_at=invalidated_at,
                invalidation_reasons=reasons,
                knowledge_readiness_state="STALE",
                unit_map_hash=next_hash,
            )
        )

    async def set_unit_knowledge_state(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        unit_map_id: UUID,
        readiness_state: str,
        challenge_state: str,
        reason: str | None,
        updated_at: datetime,
    ) -> None:
        current = await self.get_unit_map(
            connection, project_id=project_id, unit_map_id=unit_map_id
        )
        if current is None or current.invalidated_at is not None:
            return
        reasons = list(current.invalidation_reasons)
        if reason is not None and reason not in reasons:
            reasons.append(reason)
        if reason is None:
            reasons = [
                item for item in reasons if not item.startswith("CANON_CHALLENGE:")
            ]
        next_hash = _unit_map_hash(
            current,
            knowledge_readiness_state=readiness_state,
            challenge_state=challenge_state,
            invalidation_reasons=reasons,
        )
        await connection.execute(
            update(vekl_unit_maps)
            .where(
                vekl_unit_maps.c.project_id == project_id,
                vekl_unit_maps.c.unit_map_id == unit_map_id,
                vekl_unit_maps.c.invalidated_at.is_(None),
            )
            .values(
                knowledge_readiness_state=readiness_state,
                challenge_state=challenge_state,
                invalidation_reasons=reasons,
                unit_map_hash=next_hash,
                updated_at=updated_at,
            )
        )

    async def insert_node(
        self, connection: AsyncConnection, record: VEKLKnowledgeNode
    ) -> None:
        await connection.execute(
            vekl_knowledge_nodes.insert().values(**record.model_dump())
        )

    async def node_by_identity(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        node_kind: str,
        stable_ref: str,
        content_hash: str,
        compiler_version: str,
    ) -> VEKLKnowledgeNode | None:
        result = await connection.execute(
            select(vekl_knowledge_nodes).where(
                vekl_knowledge_nodes.c.project_id == project_id,
                vekl_knowledge_nodes.c.node_kind == node_kind,
                vekl_knowledge_nodes.c.stable_ref == stable_ref,
                vekl_knowledge_nodes.c.content_hash == content_hash,
                vekl_knowledge_nodes.c.projection_compiler_version == compiler_version,
            )
        )
        row = result.mappings().first()
        return None if row is None else VEKLKnowledgeNode.model_validate(dict(row))

    async def list_active_nodes(
        self, connection: AsyncConnection, *, project_id: UUID
    ) -> list[VEKLKnowledgeNode]:
        result = await connection.execute(
            select(vekl_knowledge_nodes)
            .where(
                vekl_knowledge_nodes.c.project_id == project_id,
                vekl_knowledge_nodes.c.invalidated_at.is_(None),
            )
            .order_by(vekl_knowledge_nodes.c.knowledge_node_id)
        )
        return [
            VEKLKnowledgeNode.model_validate(dict(row)) for row in result.mappings()
        ]

    async def insert_edge(
        self, connection: AsyncConnection, record: VEKLKnowledgeEdge
    ) -> None:
        await connection.execute(
            vekl_knowledge_edges.insert().values(**record.model_dump())
        )

    async def edge_by_identity(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        from_node_id: UUID,
        relationship: str,
        to_node_id: UUID,
        provenance_hash: str,
    ) -> VEKLKnowledgeEdge | None:
        result = await connection.execute(
            select(vekl_knowledge_edges).where(
                vekl_knowledge_edges.c.project_id == project_id,
                vekl_knowledge_edges.c.from_node_id == from_node_id,
                vekl_knowledge_edges.c.relationship == relationship,
                vekl_knowledge_edges.c.to_node_id == to_node_id,
                vekl_knowledge_edges.c.provenance_hash == provenance_hash,
            )
        )
        row = result.mappings().first()
        return None if row is None else VEKLKnowledgeEdge.model_validate(dict(row))

    async def list_active_edges(
        self, connection: AsyncConnection, *, project_id: UUID
    ) -> list[VEKLKnowledgeEdge]:
        result = await connection.execute(
            select(vekl_knowledge_edges)
            .where(
                vekl_knowledge_edges.c.project_id == project_id,
                vekl_knowledge_edges.c.invalidated_at.is_(None),
            )
            .order_by(vekl_knowledge_edges.c.knowledge_edge_id)
        )
        return [
            VEKLKnowledgeEdge.model_validate(dict(row)) for row in result.mappings()
        ]

    async def insert_route(
        self, connection: AsyncConnection, record: VEKLRetrievalRoute
    ) -> None:
        await connection.execute(
            vekl_retrieval_routes.insert().values(**record.model_dump())
        )

    async def route_by_hash(
        self, connection: AsyncConnection, *, project_id: UUID, policy_hash: str
    ) -> VEKLRetrievalRoute | None:
        result = await connection.execute(
            select(vekl_retrieval_routes).where(
                vekl_retrieval_routes.c.project_id == project_id,
                vekl_retrieval_routes.c.policy_hash == policy_hash,
            )
        )
        row = result.mappings().first()
        return None if row is None else VEKLRetrievalRoute.model_validate(dict(row))

    async def list_active_routes(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        concerns: list[str] | None = None,
    ) -> list[VEKLRetrievalRoute]:
        query = select(vekl_retrieval_routes).where(
            vekl_retrieval_routes.c.project_id == project_id,
            vekl_retrieval_routes.c.active.is_(True),
        )
        if concerns:
            query = query.where(vekl_retrieval_routes.c.concern.in_(concerns))
        result = await connection.execute(
            query.order_by(
                vekl_retrieval_routes.c.concern, vekl_retrieval_routes.c.route_slug
            )
        )
        return [
            VEKLRetrievalRoute.model_validate(dict(row)) for row in result.mappings()
        ]

    async def insert_finding(
        self, connection: AsyncConnection, record: VEKLResearchFinding
    ) -> None:
        await connection.execute(
            vekl_research_findings.insert().values(**record.model_dump())
        )

    async def get_finding(
        self, connection: AsyncConnection, *, project_id: UUID, finding_id: UUID
    ) -> VEKLResearchFinding | None:
        result = await connection.execute(
            select(vekl_research_findings).where(
                vekl_research_findings.c.project_id == project_id,
                vekl_research_findings.c.finding_id == finding_id,
            )
        )
        row = result.mappings().first()
        return None if row is None else VEKLResearchFinding.model_validate(dict(row))

    async def list_findings_for_unit(
        self, connection: AsyncConnection, *, project_id: UUID, unit_map_id: UUID
    ) -> list[VEKLResearchFinding]:
        result = await connection.execute(
            select(vekl_research_findings)
            .where(
                vekl_research_findings.c.project_id == project_id,
                vekl_research_findings.c.unit_map_id == unit_map_id,
            )
            .order_by(vekl_research_findings.c.created_at)
        )
        return [
            VEKLResearchFinding.model_validate(dict(row)) for row in result.mappings()
        ]

    async def insert_conflict_observation(
        self, connection: AsyncConnection, record: VEKLConflictObservation
    ) -> None:
        await connection.execute(
            vekl_conflict_observations.insert().values(**record.model_dump())
        )

    async def list_conflict_observations(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        truth_hash: str | None = None,
    ) -> list[VEKLConflictObservation]:
        query = select(vekl_conflict_observations).where(
            vekl_conflict_observations.c.project_id == project_id
        )
        if truth_hash is not None:
            query = query.where(
                vekl_conflict_observations.c.current_truth_hash == truth_hash
            )
        result = await connection.execute(
            query.order_by(vekl_conflict_observations.c.created_at)
        )
        return [
            VEKLConflictObservation.model_validate(dict(row))
            for row in result.mappings()
        ]

    async def insert_challenge(
        self, connection: AsyncConnection, record: VEKLTruthChallenge
    ) -> None:
        await connection.execute(
            vekl_truth_challenges.insert().values(**record.model_dump())
        )

    async def get_challenge(
        self, connection: AsyncConnection, *, project_id: UUID, challenge_id: UUID
    ) -> VEKLTruthChallenge | None:
        result = await connection.execute(
            select(vekl_truth_challenges).where(
                vekl_truth_challenges.c.project_id == project_id,
                vekl_truth_challenges.c.challenge_id == challenge_id,
            )
        )
        row = result.mappings().first()
        return None if row is None else VEKLTruthChallenge.model_validate(dict(row))

    async def challenge_by_hash(
        self, connection: AsyncConnection, *, project_id: UUID, challenge_hash: str
    ) -> VEKLTruthChallenge | None:
        result = await connection.execute(
            select(vekl_truth_challenges).where(
                vekl_truth_challenges.c.project_id == project_id,
                vekl_truth_challenges.c.challenge_hash == challenge_hash,
            )
        )
        row = result.mappings().first()
        return None if row is None else VEKLTruthChallenge.model_validate(dict(row))

    async def update_challenge(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        challenge_id: UUID,
        fields: dict[str, object],
    ) -> None:
        await connection.execute(
            update(vekl_truth_challenges)
            .where(
                vekl_truth_challenges.c.project_id == project_id,
                vekl_truth_challenges.c.challenge_id == challenge_id,
            )
            .values(**fields)
        )

    async def list_challenges(
        self, connection: AsyncConnection, *, project_id: UUID
    ) -> list[VEKLTruthChallenge]:
        result = await connection.execute(
            select(vekl_truth_challenges)
            .where(vekl_truth_challenges.c.project_id == project_id)
            .order_by(vekl_truth_challenges.c.created_at.desc())
        )
        return [
            VEKLTruthChallenge.model_validate(dict(row)) for row in result.mappings()
        ]

    async def insert_challenge_finding(
        self, connection: AsyncConnection, record: VEKLTruthChallengeFinding
    ) -> None:
        await connection.execute(
            vekl_truth_challenge_findings.insert().values(**record.model_dump())
        )

    async def insert_graph_invalidation(
        self, connection: AsyncConnection, record: VEKLGraphInvalidation
    ) -> None:
        await connection.execute(
            vekl_graph_invalidations.insert().values(**record.model_dump())
        )

    async def list_invalidations(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        unit_map_id: UUID | None = None,
    ) -> list[VEKLGraphInvalidation]:
        query = select(vekl_graph_invalidations).where(
            vekl_graph_invalidations.c.project_id == project_id
        )
        if unit_map_id is not None:
            query = query.where(vekl_graph_invalidations.c.unit_map_id == unit_map_id)
        result = await connection.execute(
            query.order_by(vekl_graph_invalidations.c.created_at)
        )
        return [
            VEKLGraphInvalidation.model_validate(dict(row)) for row in result.mappings()
        ]

    async def insert_resolution_trace(
        self, connection: AsyncConnection, record: VEKLResolutionTrace
    ) -> None:
        await connection.execute(
            vekl_resolution_traces.insert().values(**record.model_dump())
        )

    async def get_resolution_trace(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        resolution_trace_id: UUID,
    ) -> VEKLResolutionTrace | None:
        result = await connection.execute(
            select(vekl_resolution_traces).where(
                vekl_resolution_traces.c.project_id == project_id,
                vekl_resolution_traces.c.resolution_trace_id == resolution_trace_id,
            )
        )
        row = result.mappings().first()
        return None if row is None else VEKLResolutionTrace.model_validate(dict(row))

    async def trace_by_hash(
        self, connection: AsyncConnection, *, project_id: UUID, trace_hash: str
    ) -> VEKLResolutionTrace | None:
        result = await connection.execute(
            select(vekl_resolution_traces).where(
                vekl_resolution_traces.c.project_id == project_id,
                vekl_resolution_traces.c.trace_hash == trace_hash,
            )
        )
        row = result.mappings().first()
        return None if row is None else VEKLResolutionTrace.model_validate(dict(row))

    async def list_resolution_traces(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        unit_map_id: UUID | None = None,
    ) -> list[VEKLResolutionTrace]:
        query = select(vekl_resolution_traces).where(
            vekl_resolution_traces.c.project_id == project_id
        )
        if unit_map_id is not None:
            query = query.where(vekl_resolution_traces.c.unit_map_id == unit_map_id)
        result = await connection.execute(
            query.order_by(
                vekl_resolution_traces.c.created_at,
                vekl_resolution_traces.c.resolution_trace_id,
            )
        )
        return [
            VEKLResolutionTrace.model_validate(dict(row)) for row in result.mappings()
        ]

    async def insert_execution_binding(
        self, connection: AsyncConnection, record: VEKLExecutionKnowledgeBinding
    ) -> None:
        await connection.execute(
            vekl_execution_knowledge_bindings.insert().values(**record.model_dump())
        )

    async def execution_binding_for_stage(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        resolution_trace_id: UUID,
        binding_stage: str,
    ) -> VEKLExecutionKnowledgeBinding | None:
        result = await connection.execute(
            select(vekl_execution_knowledge_bindings).where(
                vekl_execution_knowledge_bindings.c.project_id == project_id,
                vekl_execution_knowledge_bindings.c.resolution_trace_id
                == resolution_trace_id,
                vekl_execution_knowledge_bindings.c.binding_stage == binding_stage,
            )
        )
        row = result.mappings().first()
        return (
            None
            if row is None
            else VEKLExecutionKnowledgeBinding.model_validate(dict(row))
        )

    async def get_execution_binding(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        execution_binding_id: UUID,
    ) -> VEKLExecutionKnowledgeBinding | None:
        result = await connection.execute(
            select(vekl_execution_knowledge_bindings).where(
                vekl_execution_knowledge_bindings.c.project_id == project_id,
                vekl_execution_knowledge_bindings.c.execution_binding_id
                == execution_binding_id,
            )
        )
        row = result.mappings().first()
        return (
            None
            if row is None
            else VEKLExecutionKnowledgeBinding.model_validate(dict(row))
        )

    async def list_execution_bindings(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        resolution_trace_id: UUID,
    ) -> list[VEKLExecutionKnowledgeBinding]:
        result = await connection.execute(
            select(vekl_execution_knowledge_bindings)
            .where(
                vekl_execution_knowledge_bindings.c.project_id == project_id,
                vekl_execution_knowledge_bindings.c.resolution_trace_id
                == resolution_trace_id,
            )
            .order_by(
                vekl_execution_knowledge_bindings.c.created_at,
                vekl_execution_knowledge_bindings.c.execution_binding_id,
            )
        )
        return [
            VEKLExecutionKnowledgeBinding.model_validate(dict(row))
            for row in result.mappings()
        ]
