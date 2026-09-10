"""End-to-end Production VEKL 2.2 graph, execution binding and truth evolution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.context.model import ContextBudgetExceeded
from engine.contracts.stack_fingerprint import StackFingerprint
from engine.contracts.task_signature import TaskSignature
from engine.contracts.vekl_resource import VEKLResource
from engine.contracts.vekl_unit_map import VEKLUnitMap
from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError
from engine.core.hashing import sha256_hex
from engine.events.service import EventService
from engine.missions.service import MissionService
from engine.truth.db import open_unit_of_work
from engine.truth.repository import TruthRepository
from engine.vekl.knowledge_repository import VEKLKnowledgeRepository
from engine.vekl.knowledge_service import VEKLKnowledgeService
from engine.vekl.models import ActivationPlanSpec, TaskSignatureSpec, VEKLResourceSpec
from engine.vekl.service import VEKLService
from engine.workspaces.repository import WorkspaceRepository
from tests.support.db import new_engine
from tests.support.execution_fixtures import ExecutionFixture, build_execution_fixture

MODE = "APPLICATION_MANUFACTURING_VEKL"
pytestmark = pytest.mark.integration


async def _classify_target(engine: AsyncEngine, fixture: ExecutionFixture) -> None:
    async with open_unit_of_work(
        engine,
        tenant_id=fixture.tenant.tenant_id,
        project_id=fixture.tenant.project_id,
    ) as uow:
        await uow.connection.execute(
            text("UPDATE projects SET kind='TARGET_APPLICATION' WHERE project_id=:p"),
            {"p": fixture.tenant.project_id},
        )
        await uow.commit()


async def _workspace(
    engine: AsyncEngine, fixture: ExecutionFixture, root: Path
) -> Workspace:
    (root / "package.json").write_text(
        '{"packageManager":"pnpm@10.0.0","dependencies":{"react":"19.2.8"}}'
    )
    (root / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
    now = datetime.now(UTC)
    workspace = Workspace(
        workspace_id=uuid4(),
        tenant_id=fixture.tenant.tenant_id,
        project_id=fixture.tenant.project_id,
        mission_id=fixture.mission.mission_id,
        task_id=fixture.task.task_id,
        execution_environment_id=None,
        base_revision="base",
        current_revision="head",
        workspace_path=str(root),
        policy={},
        status="READY",
        lock_version=1,
        created_at=now,
        updated_at=now,
    )
    async with open_unit_of_work(
        engine,
        tenant_id=fixture.tenant.tenant_id,
        project_id=fixture.tenant.project_id,
    ) as uow:
        await WorkspaceRepository().insert_workspace(uow.connection, workspace)
        await uow.commit()
    return workspace


async def _qualified_resource(
    service: VEKLService, fixture: ExecutionFixture
) -> VEKLResource:
    excerpt = "Pinned backend implementation guidance for the routing service."
    resource = await service.register_resource(
        tenant_id=fixture.tenant.tenant_id,
        project_id=fixture.tenant.project_id,
        request_mode=MODE,
        spec=VEKLResourceSpec(
            resource_kind="OFFICIAL_DOC",
            title="Backend implementation reference",
            publisher="DDE fixture publisher",
            revision="1.0.0",
            content_hash=sha256_hex(excerpt),
            source_trust="S2_FIRST_PARTY",
            reuse_class="SOURCE_REFERENCE_ONLY",
            activation_modes=["READ_ONLY_CONTEXT"],
            license_ids=["MIT"],
            provenance={"hash_verified": True, "purpose": "backend-guidance"},
            content_excerpt=excerpt,
        ),
    )
    for state in ("METADATA_VERIFIED", "REFERENCE_QUALIFIED"):
        resource = await service.transition_resource(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            resource_id=resource.resource_id,
            to_state=state,
            request_mode=MODE,
        )
    return resource


@dataclass(frozen=True)
class PreparedKnowledge:
    service: VEKLService
    knowledge: VEKLKnowledgeService
    workspace: Workspace
    fingerprint: StackFingerprint
    signature: TaskSignature
    resource: VEKLResource
    unit: VEKLUnitMap


async def _prepared(
    engine: AsyncEngine, fixture: ExecutionFixture, root: Path
) -> PreparedKnowledge:
    await _classify_target(engine, fixture)
    service = VEKLService(engine)
    knowledge = VEKLKnowledgeService(engine)
    workspace = await _workspace(engine, fixture, root)
    fingerprint = await service.build_stack_fingerprint_from_workspace(
        tenant_id=fixture.tenant.tenant_id,
        project_id=fixture.tenant.project_id,
        workspace_id=workspace.workspace_id,
        request_mode=MODE,
    )
    signature = await service.build_task_signature(
        task=fixture.task,
        fingerprint=fingerprint,
        spec=TaskSignatureSpec(
            lifecycle_stage="implementation", budget={"tokens": 5000}
        ),
    )
    resource = await _qualified_resource(service, fixture)
    units = await knowledge.compile_units_for_graph(
        tenant_id=fixture.tenant.tenant_id,
        project_id=fixture.tenant.project_id,
        task_graph_id=fixture.task.graph_id,
        stack_fingerprint_id=fingerprint.fingerprint_id,
        request_mode=MODE,
    )
    unit = next(item for item in units if fixture.task.task_id in item.task_ids)
    return PreparedKnowledge(
        service=service,
        knowledge=knowledge,
        workspace=workspace,
        fingerprint=fingerprint,
        signature=signature,
        resource=resource,
        unit=unit,
    )


@pytest.mark.asyncio
async def test_graph_resolution_binds_exact_manifest_and_context_append_only(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    try:
        fixture = await build_execution_fixture(
            engine, tmp_path, mission_slug=f"vekl-graph-{uuid4().hex}"
        )
        prepared = await _prepared(engine, fixture, tmp_path)
        service = prepared.service
        knowledge = prepared.knowledge
        fingerprint = prepared.fingerprint
        signature = prepared.signature
        resource = prepared.resource
        unit = prepared.unit
        first_graph = await knowledge.compile_graph(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            unit_map_id=unit.unit_map_id,
            request_mode=MODE,
        )
        second_graph = await knowledge.compile_graph(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            unit_map_id=unit.unit_map_id,
            request_mode=MODE,
        )
        assert first_graph["graph_snapshot_hash"] == second_graph["graph_snapshot_hash"]
        trace = await knowledge.resolve_knowledge(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            unit_map_id=unit.unit_map_id,
            task_id=fixture.task.task_id,
            task_signature_id=signature.signature_id,
            requested_modes=["READ_ONLY_CONTEXT"],
            available_capabilities=[],
            available_verifiers=[],
            sandbox_available=True,
            offline=False,
            request_mode=MODE,
        )
        selected = {
            item["resource_id"]
            for item in trace.candidate_decisions
            if item.get("selected") is True
        }
        assert str(resource.resource_id) in selected
        manifest = await service.plan_activation(
            task=fixture.task,
            fingerprint=fingerprint,
            signature=signature,
            spec=ActivationPlanSpec(
                request_mode=MODE,
                policy={"version": "knowledge-e2e"},
                requested_modes=["READ_ONLY_CONTEXT"],
                mandatory_resource_ids=[resource.resource_id],
                resolution_trace_id=trace.resolution_trace_id,
                resolved_resource_ids=[resource.resource_id],
                sandbox_available=True,
            ),
        )
        activation_binding = await knowledge.bind_execution(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            resolution_trace_id=trace.resolution_trace_id,
            manifest_id=manifest.manifest_id,
            manifest_hash=manifest.manifest_hash,
            context_package_id=None,
            context_package_hash=None,
            context_capsule_hashes=[],
            request_mode=MODE,
        )
        worker_context = await service.compile_worker_context(
            task=fixture.task,
            manifest=manifest,
            context_budget_tokens=24000,
        )
        context_package = worker_context.context_package
        assert not isinstance(context_package, ContextBudgetExceeded), context_package
        context_binding = await knowledge.bind_execution(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            resolution_trace_id=trace.resolution_trace_id,
            manifest_id=manifest.manifest_id,
            manifest_hash=manifest.manifest_hash,
            context_package_id=context_package.package_id,
            context_package_hash=context_package.assembly_hash,
            context_capsule_hashes=[worker_context.capsule.capsule_hash],
            request_mode=MODE,
        )
        assert activation_binding.binding_stage == "ACTIVATION_BOUND"
        assert context_binding.binding_stage == "CONTEXT_BOUND"
        assert activation_binding.binding_hash != context_binding.binding_hash
        fresh = await knowledge.require_fresh_execution_binding(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            execution_binding_id=context_binding.execution_binding_id,
            request_mode=MODE,
        )
        assert fresh.binding_hash == context_binding.binding_hash
        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            persisted_trace = await VEKLKnowledgeRepository().get_resolution_trace(
                uow.connection,
                project_id=fixture.tenant.project_id,
                resolution_trace_id=trace.resolution_trace_id,
            )
            bindings = await VEKLKnowledgeRepository().list_execution_bindings(
                uow.connection,
                project_id=fixture.tenant.project_id,
                resolution_trace_id=trace.resolution_trace_id,
            )
        assert persisted_trace == trace
        assert [item.binding_stage for item in bindings] == [
            "ACTIVATION_BOUND",
            "CONTEXT_BOUND",
        ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_critical_truth_challenge_blocks_then_truth_change_invalidates_unit(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    try:
        fixture = await build_execution_fixture(
            engine, tmp_path, mission_slug=f"vekl-challenge-{uuid4().hex}"
        )
        prepared = await _prepared(engine, fixture, tmp_path)
        knowledge = prepared.knowledge
        resource = prepared.resource
        unit = prepared.unit
        finding = await knowledge.record_research_finding(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            unit_map_id=unit.unit_map_id,
            task_refs=[fixture.task.task_id],
            concern="BACKEND_API",
            source_id=None,
            source_artifact_id=None,
            resource_id=resource.resource_id,
            source_trust=resource.source_trust,
            source_revision=resource.revision,
            content_hash=resource.content_hash,
            claim="The accepted requirement needs a newer compatibility constraint.",
            supporting_excerpt_hash=sha256_hex("compatibility evidence"),
            freshness={"stale": False, "deterministic_reproduction": True},
            classification="TRUTH_CONFLICT_SIGNAL",
            confidence="HIGH",
            corroboration_refs=[],
            project_truth_refs=list(fixture.task.requirement_refs),
            stack_refs=[unit.stack_fingerprint_hash],
            impact_hypothesis=["routing behaviour changes"],
            request_mode=MODE,
        )
        slug = f"REQ-VEKL-{uuid4().hex[:10]}"
        challenge = await knowledge.create_truth_challenge(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.mission.mission_id,
            task_id=fixture.task.task_id,
            finding_ids=[finding.finding_id],
            challenge_class="COMPATIBILITY_CHALLENGE",
            severity="CRITICAL",
            conflict={"summary": "compatibility mismatch"},
            confidence={"level": "HIGH"},
            impact={"tasks": [str(fixture.task.task_id)]},
            proposal={
                "truth_change_kind": "REQUIREMENT_ADD",
                "exact_truth_patch": {
                    "slug": slug,
                    "statement": (
                        "The routing implementation shall honor the pinned "
                        "compatibility contract."
                    ),
                    "constraints": ["compatibility:pinned"],
                    "acceptance_conditions": ["Pinned compatibility is verified"],
                },
                "migration_plan": {"steps": ["recompile affected units"]},
                "verification_plan": {"tests": ["contract", "integration"]},
            },
            decision_analysis={"recommended": "ACCEPT"},
            reopen_conditions=["new normative evidence"],
            requested_by=fixture.tenant.principal_id,
            idempotency_key=f"challenge-{uuid4().hex}",
            request_mode=MODE,
        )
        mission_service = MissionService(engine, EventService(engine))
        blocked = await mission_service.get_task(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            task_id=fixture.task.task_id,
        )
        assert blocked.status == "BLOCKED_ON_DECISION"
        decided = await knowledge.decide_truth_challenge(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            challenge_id=challenge.challenge_id,
            decision="ACCEPT",
            reason="Evidence establishes the exact replacement requirement.",
            decided_by=fixture.tenant.principal_id,
            request_mode=MODE,
        )
        assert decided.status == "TRUTH_CHANGED"
        unblocked = await mission_service.get_task(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            task_id=fixture.task.task_id,
        )
        assert unblocked.status == "READY"
        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            requirement = await TruthRepository().get_requirement_by_slug(
                uow.connection, fixture.tenant.project_id, slug
            )
            invalidated = await VEKLKnowledgeRepository().get_unit_map(
                uow.connection,
                project_id=fixture.tenant.project_id,
                unit_map_id=unit.unit_map_id,
            )
        assert requirement is not None and requirement.status == "approved"
        assert invalidated is not None and invalidated.invalidated_at is not None
        with pytest.raises(DdeError) as stale:
            await knowledge.compile_graph(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                unit_map_id=unit.unit_map_id,
                request_mode=MODE,
            )
        assert stale.value.error_code == "VEKL_KNOWLEDGE_STALE"
    finally:
        await engine.dispose()
