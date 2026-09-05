"""PostgreSQL lifecycle proof for DDE-069 M8 Source Intelligence.

This integration spec keeps external providers out of the proof: the versioned
DDE library supplies exact repository bytes, while PostgreSQL proves durable
search/admission/provenance/score/promotion/audit state. A host without the
configured PostgreSQL service must leave this test collected but unexecuted.
"""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from engine.contracts.pxg_node import SourceRef
from engine.contracts.verification_run import CheckResult, VerificationRun
from engine.object_store.durable import LocalScopedObjectStore
from engine.studio.audit.reads import ScreenAuditReadService
from engine.studio.audit.service import ScreenAuditService
from engine.studio.candidates.lifecycle import CandidateState
from engine.studio.candidates.promotion import PromotionService
from engine.studio.candidates.service import CandidateService
from engine.studio.mutations.executor import MutationExecutor
from engine.studio.mutations.planner import MutationRequest
from engine.studio.pxg.service import NodeInput, PxgService
from engine.studio.source.adapters import DdeLibrarySourceAdapter
from engine.studio.source.service import SourceIntelligenceService
from engine.studio.source.tables import design_source_search_runs
from engine.truth.db import open_unit_of_work
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine, seed_tenant


class _Scope(TypedDict):
    tenant_id: UUID
    project_id: UUID


def _passing_visual_run() -> VerificationRun:
    now = datetime.now(UTC)
    return VerificationRun(
        verification_run_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        mission_id=uuid4(),
        task_id=uuid4(),
        task_attempt_id=uuid4(),
        worker_run_id=uuid4(),
        workspace_id=uuid4(),
        oracle_id=uuid4(),
        sequence=1,
        status="PASSED",
        confidence=1.0,
        check_results=[
            CheckResult(
                check_ref=f"screens/checkout:{kind}",
                kind=kind,
                command=[],
                exit_code=0,
                stdout="",
                stderr="",
                duration_ms=1,
                timed_out=False,
                status="PASSED",
            )
            for kind in ("silhouette", "visual_critique")
        ],
        outcome_results=[],
        negative_case_results=[],
        evidence_refs=[],
        started_at=now,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_m8_source_lifecycle_persists_through_promotion_and_audit(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    workspace_service = WorkspaceService(engine)
    workspace = None
    try:
        fixture = await seed_tenant(engine)
        scope: _Scope = {
            "tenant_id": fixture.tenant_id,
            "project_id": fixture.project_id,
        }
        await PxgService(engine).apply(
            **scope,
            nodes=[
                NodeInput(
                    pxg_key="screens/checkout",
                    node_kind="screen",
                    title="Checkout",
                    source_refs=(SourceRef(path="src/Checkout.tsx"),),
                    attributes={
                        "bound_verification_kinds": ["silhouette", "visual_critique"]
                    },
                    provenance={"source_revision": "git:m8-postgres-fixture"},
                ),
                NodeInput(
                    pxg_key="screens/checkout#hero",
                    node_kind="region",
                    title="Hero",
                    parent_key="screens/checkout",
                    attributes={"spacing": "space2"},
                ),
            ],
        )
        audit = ScreenAuditService(engine)
        first_audit = await audit.run(**scope, mission_id=None, trigger="FULL")
        first_matrix = await ScreenAuditReadService(engine).matrix(**scope)
        checkout_before = next(
            row for row in first_matrix.screens if row.pxg_key == "screens/checkout"
        )
        assert checkout_before.dimension_states["SOURCE_PROVENANCE"] == "PARTIAL"

        sources = SourceIntelligenceService(
            engine,
            adapters={"dde-library": DdeLibrarySourceAdapter()},
            object_store=LocalScopedObjectStore(
                namespace="source-artifacts", root=tmp_path / "objects"
            ),
            workspaces=workspace_service,
        )
        inventory = await sources.ensure_sources(**scope)
        dde_library = next(
            row for row in inventory if row.provider_key == "dde-library"
        )
        assert dde_library.status == "AVAILABLE"
        assert next(row for row in inventory if row.provider_key == "21st").status == (
            "NOT_CONFIGURED"
        )

        searched = await sources.search(
            **scope,
            mission_id=None,
            query="marketplace",
            provider_keys=("dde-library",),
        )
        assert searched.run.status == "COMPLETED"
        assert searched.run.result_count == 1
        assert len(searched.artifacts) == 1
        async with open_unit_of_work(engine, **scope) as uow:
            persisted_run = (
                (
                    await uow.connection.execute(
                        select(design_source_search_runs).where(
                            design_source_search_runs.c.search_run_id
                            == searched.run.search_run_id
                        )
                    )
                )
                .mappings()
                .one()
            )
        assert persisted_run["status"] == "COMPLETED"
        assert persisted_run["result_count"] == 1

        indexed = searched.artifacts[0]
        inspected = await sources.inspect(**scope, artifact_id=indexed.artifact_id)
        assert inspected.provider_artifact_key == "dde.foundation.marketplace.v1"
        fetched = await sources.fetch(**scope, artifact_id=indexed.artifact_id)
        assert fetched.content is not None
        assert fetched.artifact.content_object_backend == "LOCAL"
        assert fetched.artifact.content_hash is not None

        candidate, workspace, sandboxed, _path = await sources.sandbox_adapt(
            **scope,
            mission_id=None,
            artifact_id=fetched.artifact.artifact_id,
            scope_keys=("screens/checkout",),
        )
        assert candidate.origin == "SOURCE_IMPORT"
        assert candidate.state == "READY"
        admission, candidate_provenance = await sources.validate_sandbox(
            **scope, artifact_id=sandboxed.artifact_id
        )
        assert admission.state == "ADMITTED"
        assert not admission.hard_failures
        assert candidate_provenance is not None
        assert candidate_provenance.subject_kind == "CANDIDATE"
        assert candidate_provenance.subject_ref == str(candidate.candidate_id)
        assert candidate_provenance.admission_id == admission.admission_id

        executor = MutationExecutor(engine)
        outcome = await executor.apply(
            **scope,
            candidate_id=candidate.candidate_id,
            requests=[
                MutationRequest(
                    operation="SET_PROPERTY",
                    target_key="screens/checkout#hero",
                    origin="INSPECTOR",
                    payload={"property": "spacing", "value": "space6"},
                )
            ],
        )
        assert outcome.fully_applied
        assert outcome.candidate_state is CandidateState.DIRTY

        score = await sources.compute_candidate_score(
            **scope, candidate_id=candidate.candidate_id
        )
        assert score.score_state == "UNSCORED"
        assert score.overall_score is None
        assert score.classification == "UNSCORED"
        ready, detail = await sources.promotion_readiness(
            **scope,
            candidate_id=candidate.candidate_id,
            candidate_origin=candidate.origin,
        )
        assert ready, detail

        candidates = CandidateService(engine)
        for target in (
            CandidateState.VERIFYING,
            CandidateState.VERIFIED,
            CandidateState.PROMOTABLE,
        ):
            await candidates.transition(
                **scope, candidate_id=candidate.candidate_id, target=target
            )

        visual_run = _passing_visual_run()
        promotion = PromotionService(engine, sources=sources)
        decision = await promotion.evaluate(
            **scope,
            candidate_id=candidate.candidate_id,
            verification_runs=(visual_run,),
        )
        assert decision.allowed, decision.reason
        assert next(g for g in decision.gates if g.name == "source_provenance").passed

        promoted = await promotion.promote(
            **scope,
            candidate_id=candidate.candidate_id,
            verification_runs=(visual_run,),
        )
        assert promoted.state == "PROMOTED"
        accepted = await PxgService(engine).load(**scope)
        hero = accepted.node_by_key("screens/checkout#hero")
        assert hero is not None and hero.attributes["spacing"] == "space6"

        carried = await sources.carry_candidate_provenance_to_pxg(
            **scope,
            candidate_id=candidate.candidate_id,
            scope_keys=tuple(promoted.scope_keys),
            accepted_revision=f"pxg:{accepted.revision}",
        )
        assert carried
        assert all(row.subject_kind == "PXG_NODE" for row in carried)
        assert all(row.subject_ref == "screens/checkout" for row in carried)
        assert all(
            row.metadata["promoted_from_candidate_id"] == str(candidate.candidate_id)
            for row in carried
        )

        invalidated = await audit.invalidate_affected(
            **scope, affected_keys=("screens/checkout",)
        )
        assert invalidated > 0
        previous = await audit.latest_run(**scope, include_stale=True)
        assert (
            previous is not None
            and previous.audit_run_id == first_audit.run.audit_run_id
        )
        assert previous.stale

        rerun = await audit.run(
            **scope,
            mission_id=None,
            trigger="PROMOTION",
            affected_keys=("screens/checkout",),
        )
        assert rerun.run.status in {"COMPLETED", "BLOCKED"}
        matrix = await ScreenAuditReadService(engine).matrix(**scope)
        checkout_after = next(
            row for row in matrix.screens if row.pxg_key == "screens/checkout"
        )
        assert checkout_after.dimension_states["SOURCE_PROVENANCE"] == "PASS"
        accepted_provenance = await sources.provenance_for_subject(
            **scope,
            subject_kind="PXG_NODE",
            subject_ref="screens/checkout",
        )
        assert accepted_provenance
        assert all(
            row.admission_id == admission.admission_id for row in accepted_provenance
        )
    finally:
        if workspace is not None:
            with suppress(Exception):
                await workspace_service.cleanup(workspace=workspace)
        await engine.dispose()
