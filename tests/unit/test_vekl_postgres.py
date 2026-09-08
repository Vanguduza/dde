"""Persistent Production VEKL activation, failover and isolation proof."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.context_package import ContextPackage
from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError
from engine.core.hashing import sha256_hex
from engine.truth.db import open_unit_of_work
from engine.vekl.models import (
    ActivationPlanSpec,
    ResourceOutcomeSpec,
    TaskSignatureSpec,
    VEKLResourceSpec,
)
from engine.vekl.service import VEKLService
from engine.workspaces.repository import WorkspaceRepository
from tests.support.context_fixtures import ContextFixture, build_context_fixture
from tests.support.db import new_engine

MODE = "APPLICATION_MANUFACTURING_VEKL"
pytestmark = pytest.mark.integration


async def classify_project(
    engine: AsyncEngine, fixture: ContextFixture, kind: str
) -> None:
    async with open_unit_of_work(
        engine,
        tenant_id=fixture.tenant.tenant_id,
        project_id=fixture.tenant.project_id,
    ) as uow:
        await uow.connection.execute(
            text("UPDATE projects SET kind=:kind WHERE project_id=:project_id"),
            {"kind": kind, "project_id": fixture.tenant.project_id},
        )
        await uow.commit()


async def seed_stack_workspace(
    engine: AsyncEngine, fixture: ContextFixture, root: Path
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
        base_revision="test-base",
        current_revision="test-head",
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


def docs_spec(**changes: object) -> VEKLResourceSpec:
    excerpt = "Pinned React 19 exact-version build guidance."
    values: dict[str, object] = {
        "resource_kind": "OFFICIAL_DOC",
        "title": "React 19 docs",
        "publisher": "React",
        "revision": "19.2.8",
        "content_hash": sha256_hex(excerpt),
        "source_trust": "S2_FIRST_PARTY",
        "reuse_class": "SOURCE_REFERENCE_ONLY",
        "activation_modes": ["READ_ONLY_CONTEXT"],
        "exact_versions": {"react": "19.2.8"},
        "license_ids": ["MIT"],
        "provenance": {
            "source": "operator-materialized exact pin",
            "hash_verified": True,
            "offline_pin_available": True,
            "purpose": "react-docs",
        },
        "required_verifiers": ["pytest"],
        "budget": {"tokens": 50},
        "content_excerpt": excerpt,
    }
    values.update(changes)
    return VEKLResourceSpec.model_validate(values)


@pytest.mark.asyncio
async def test_persistent_manifest_failover_revocation_and_historical_audit(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    try:
        fixture = await build_context_fixture(
            engine, mission_slug=f"vekl-{uuid4().hex}"
        )
        await classify_project(engine, fixture, "TARGET_APPLICATION")
        service = VEKLService(engine)
        resource = await service.register_resource(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            spec=docs_spec(),
            request_mode=MODE,
        )
        for state in ("METADATA_VERIFIED", "REFERENCE_QUALIFIED"):
            resource = await service.transition_resource(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                resource_id=resource.resource_id,
                to_state=state,
                request_mode=MODE,
            )
        workspace = await seed_stack_workspace(engine, fixture, tmp_path)
        fingerprint = await service.build_stack_fingerprint_from_workspace(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            workspace_id=workspace.workspace_id,
            request_mode=MODE,
        )
        assert fingerprint.facts["versions"] == {"react": "19.2.8"}
        assert fingerprint.facts["package_manager"] == "pnpm"
        signature = await service.build_task_signature(
            task=fixture.task,
            fingerprint=fingerprint,
            spec=TaskSignatureSpec(
                lifecycle_stage="implementation",
                required_verifiers=["pytest"],
                budget={"tokens": 500},
            ),
        )
        plan = ActivationPlanSpec(
            request_mode=MODE,
            policy={"version": "1", "offline": True},
            requested_modes=["READ_ONLY_CONTEXT"],
            mandatory_resource_ids=[resource.resource_id],
            available_verifiers=["pytest"],
            sandbox_available=True,
            offline=True,
        )
        first = await service.plan_activation(
            task=fixture.task,
            fingerprint=fingerprint,
            signature=signature,
            spec=plan,
        )
        failover = await service.plan_activation(
            task=fixture.task,
            fingerprint=fingerprint,
            signature=signature,
            spec=plan,
        )
        assert failover.manifest_id == first.manifest_id
        capsule = await service.compile_context(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            manifest=first,
            token_budget=500,
        )
        assert capsule.items[0].revision == "19.2.8"
        assert capsule.provenance_refs[0].startswith("vekl:")
        assert capsule.stack_facts["versions"] == {"react": "19.2.8"}
        worker_context = await service.compile_worker_context(
            task=fixture.task,
            manifest=first,
            context_budget_tokens=8_000,
        )
        assert isinstance(worker_context.context_package, ContextPackage)
        assert "vekl" in worker_context.context_package.retrievers_used
        extensions = worker_context.context_package.coverage.get("context_extensions")
        assert isinstance(extensions, list)
        assert extensions[0]["content_hash"] == worker_context.capsule.capsule_hash

        await service.transition_resource(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            resource_id=resource.resource_id,
            to_state="REVOKED",
            request_mode=MODE,
        )
        with pytest.raises(DdeError) as context_error:
            await service.compile_context(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                manifest=first,
                token_budget=500,
            )
        assert context_error.value.error_code == "VEKL_MANIFEST_INVALID"
        with pytest.raises(DdeError) as caught:
            await service.plan_activation(
                task=fixture.task,
                fingerprint=fingerprint,
                signature=signature,
                spec=plan,
            )
        assert caught.value.error_code == "VEKL_MANIFEST_INVALID"

        outcome = await service.record_outcome(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            manifest_id=first.manifest_id,
            spec=ResourceOutcomeSpec(
                verifier_refs=["verification:1"],
                verified_outcome="FAIL",
                regressions=["revoked-after-use"],
                iterations=1,
                latency_ms=10,
                evidence_refs=["evidence:1"],
            ),
        )
        projection = await service.projection(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        )
        assert outcome.manifest_id == first.manifest_id
        assert projection["manifests"][0]["manifest_hash"] == first.manifest_hash  # type: ignore[index]
        assert projection["invalidations"]
        assert projection["sections"]["knowledge"] == []  # type: ignore[index]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_changed_task_signature_invalidates_manifest_without_reselection(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    try:
        fixture = await build_context_fixture(
            engine, mission_slug=f"vekl-signature-{uuid4().hex}"
        )
        await classify_project(engine, fixture, "TARGET_APPLICATION")
        service = VEKLService(engine)
        resource = await service.register_resource(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            spec=docs_spec(),
            request_mode=MODE,
        )
        for state in ("METADATA_VERIFIED", "REFERENCE_QUALIFIED"):
            resource = await service.transition_resource(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                resource_id=resource.resource_id,
                to_state=state,
                request_mode=MODE,
            )
        workspace = await seed_stack_workspace(engine, fixture, tmp_path)
        fingerprint = await service.build_stack_fingerprint_from_workspace(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            workspace_id=workspace.workspace_id,
            request_mode=MODE,
        )
        first_signature = await service.build_task_signature(
            task=fixture.task,
            fingerprint=fingerprint,
            spec=TaskSignatureSpec(
                lifecycle_stage="implementation",
                constraints={"policy_variant": "one"},
                required_verifiers=["pytest"],
                budget={"tokens": 500},
            ),
        )
        plan = ActivationPlanSpec(
            request_mode=MODE,
            policy={"version": "1"},
            requested_modes=["READ_ONLY_CONTEXT"],
            mandatory_resource_ids=[resource.resource_id],
            available_verifiers=["pytest"],
            sandbox_available=True,
        )
        first = await service.plan_activation(
            task=fixture.task,
            fingerprint=fingerprint,
            signature=first_signature,
            spec=plan,
        )
        changed_signature = await service.build_task_signature(
            task=fixture.task,
            fingerprint=fingerprint,
            spec=TaskSignatureSpec(
                lifecycle_stage="implementation",
                constraints={"policy_variant": "two"},
                required_verifiers=["pytest"],
                budget={"tokens": 500},
            ),
        )
        assert changed_signature.signature_id != first_signature.signature_id
        with pytest.raises(DdeError) as caught:
            await service.plan_activation(
                task=fixture.task,
                fingerprint=fingerprint,
                signature=changed_signature,
                spec=plan,
            )
        assert caught.value.error_code == "VEKL_MANIFEST_INVALID"
        details = caught.value.details or {}
        assert details["reason"] == "VEKL_TASK_SIGNATURE_CHANGED"
        projection = await service.projection(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        )
        invalidations = projection["invalidations"]
        assert isinstance(invalidations, list)
        assert invalidations[0]["manifest_id"] == str(first.manifest_id)
        assert invalidations[0]["reason_code"] == "VEKL_TASK_SIGNATURE_CHANGED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_scope_source_and_cross_project_fail_closed() -> None:
    engine = new_engine()
    try:
        dde = await build_context_fixture(engine, mission_slug=f"dde-{uuid4().hex}")
        await classify_project(engine, dde, "DDE_CONTROL_PLANE")
        service = VEKLService(engine)
        with pytest.raises(DdeError) as scope_error:
            await service.register_resource(
                tenant_id=dde.tenant.tenant_id,
                project_id=dde.tenant.project_id,
                spec=docs_spec(),
                request_mode=MODE,
            )
        assert scope_error.value.error_code == "VEKL_SCOPE_VIOLATION"

        target = await build_context_fixture(
            engine, mission_slug=f"target-{uuid4().hex}"
        )
        await classify_project(engine, target, "TARGET_APPLICATION")
        touched = False

        async def forbidden_fetch() -> None:
            nonlocal touched
            touched = True

        with pytest.raises(DdeError) as source_error:
            await service.register_resource(
                tenant_id=target.tenant.tenant_id,
                project_id=target.tenant.project_id,
                spec=docs_spec(source_uri="https://unadmitted.example/README.md"),
                request_mode=MODE,
            )
        assert source_error.value.error_code == "VEKL_SOURCE_NOT_ADMITTED"
        assert touched is False

        projection = await service.projection(
            tenant_id=target.tenant.tenant_id,
            project_id=target.tenant.project_id,
        )
        assert projection["resources"] == []
    finally:
        await engine.dispose()
