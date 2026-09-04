"""DDE-069 Coverage service.

Computes and persists the comparison of a project's active
FrontendContract against its Project Experience Graph at a pinned PXG
revision, and answers the golden UI's coverage ring.

The service never reports a stale snapshot as current: a snapshot whose
`pxg_revision` is behind the project's is returned with that fact
attached, so the caller can recompute rather than display a number that
describes a graph nobody has any more.

This service is the sole writer of `frontend_coverage_snapshots`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.frontend_contract import FrontendContract
from engine.contracts.frontend_coverage_snapshot import (
    DimensionResult,
    Finding,
    FrontendCoverageSnapshot,
)
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.studio.contract.service import FrontendContractService
from engine.studio.coverage.scoring import (
    CoverageState,
    ObligationEvaluation,
    evaluate_obligation,
    findings_for,
    summarise,
    summarise_dimension,
)
from engine.studio.coverage.thinness import detect as detect_thinness
from engine.studio.pxg.service import PxgGraph, PxgService
from engine.studio.tables import frontend_coverage_snapshots
from engine.truth.db import open_unit_of_work


@dataclass(frozen=True)
class ComputedCoverage:
    """The result of comparing a contract against a graph."""

    state: CoverageState
    weighted_percent: float | None
    dimensions: tuple[DimensionResult, ...]
    findings: tuple[Finding, ...]


@dataclass(frozen=True)
class CoverageRead:
    """A snapshot plus whether it still describes the current graph."""

    snapshot: FrontendCoverageSnapshot | None
    current_pxg_revision: int
    stale: bool
    unavailable_reason: str | None = None


def compute(
    contract: FrontendContract,
    graph: PxgGraph,
    *,
    passing_verifications: Mapping[str, frozenset[str]] | None = None,
) -> ComputedCoverage:
    """Pure computation, so coverage can be reasoned about in a unit test
    without a database."""
    implemented = frozenset(node.pxg_key for node in graph.nodes)
    verifications = passing_verifications or {}

    evaluations: list[ObligationEvaluation] = [
        evaluate_obligation(
            obligation,
            implemented_keys=implemented,
            passing_verifications=verifications,
        )
        for obligation in contract.obligations
    ]

    by_dimension: dict[str, list[ObligationEvaluation]] = {}
    for evaluation in evaluations:
        by_dimension.setdefault(evaluation.obligation.dimension, []).append(evaluation)

    dimensions = tuple(
        summarise_dimension(dimension, items)
        for dimension, items in sorted(by_dimension.items())
    )
    state, percent = summarise(dimensions)

    findings = list(findings_for(evaluations))
    findings.extend(detect_thinness(graph))
    for node in graph.orphan_nodes():
        findings.append(
            Finding(
                finding_kind="ORPHAN_NODE",
                dimension="contract",
                pxg_key=node.pxg_key,
                obligation_id=None,
                detail=f"parent {node.parent_key!r} does not exist in the graph",
            )
        )
    for edge in graph.dangling_edges():
        findings.append(
            Finding(
                finding_kind="DANGLING_EDGE",
                dimension="navigation",
                pxg_key=edge.from_key,
                obligation_id=None,
                detail=(
                    f"{edge.edge_kind} edge points at {edge.to_key!r}, which "
                    "is not in the graph"
                ),
            )
        )
    return ComputedCoverage(
        state=state,
        weighted_percent=percent,
        dimensions=dimensions,
        findings=tuple(findings),
    )


class CoverageService:
    """Computes, persists and reads frontend coverage."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        pxg: PxgService | None = None,
        contracts: FrontendContractService | None = None,
    ) -> None:
        self._engine = engine
        self._pxg = pxg or PxgService(engine)
        self._contracts = contracts or FrontendContractService(engine)

    async def recompute(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        passing_verifications: Mapping[str, frozenset[str]] | None = None,
    ) -> FrontendCoverageSnapshot:
        contract = await self._contracts.get_active(
            tenant_id=tenant_id, project_id=project_id
        )
        if contract is None:
            raise DdeError(
                "CONTEXT_INCOMPLETE",
                "no active frontend contract; coverage is unassessable "
                "rather than zero",
                retryable=False,
                details={"project_id": str(project_id)},
            )
        graph = await self._pxg.load(tenant_id=tenant_id, project_id=project_id)
        computed = compute(contract, graph, passing_verifications=passing_verifications)
        now = datetime.now(UTC)
        record = FrontendCoverageSnapshot(
            snapshot_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            contract_id=contract.contract_id,
            contract_version=contract.contract_version,
            pxg_revision=graph.revision,
            summary_state=computed.state.value,
            weighted_percent=computed.weighted_percent,
            dimensions=list(computed.dimensions),
            findings=list(computed.findings),
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            await uow.connection.execute(
                frontend_coverage_snapshots.insert().values(
                    **record.model_dump(exclude={"dimensions", "findings"}),
                    # mode="json" so UUID obligation ids inside findings
                    # serialise into jsonb rather than failing the encoder.
                    dimensions=[
                        item.model_dump(mode="json") for item in computed.dimensions
                    ],
                    findings=[
                        item.model_dump(mode="json") for item in computed.findings
                    ],
                )
            )
            await uow.commit()
        return record

    async def latest(self, *, tenant_id: UUID, project_id: UUID) -> CoverageRead:
        """Read the newest snapshot and say plainly whether it is stale."""
        current_revision = await self._pxg.current_revision(
            tenant_id=tenant_id, project_id=project_id
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                select(frontend_coverage_snapshots)
                .where(
                    frontend_coverage_snapshots.c.tenant_id == tenant_id,
                    frontend_coverage_snapshots.c.project_id == project_id,
                )
                .order_by(frontend_coverage_snapshots.c.created_at.desc())
                .limit(1)
            )
            row = result.mappings().first()
        if row is None:
            return CoverageRead(
                snapshot=None,
                current_pxg_revision=current_revision,
                stale=False,
                unavailable_reason="NO_SNAPSHOT",
            )
        snapshot = FrontendCoverageSnapshot.model_validate(dict(row))
        return CoverageRead(
            snapshot=snapshot,
            current_pxg_revision=current_revision,
            stale=snapshot.pxg_revision < current_revision,
        )
