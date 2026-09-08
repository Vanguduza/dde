"""Production VEKL orchestration through existing truth, source and task authority."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.context.model import ContextBudgetExceeded, ContextExtension
from engine.context.service import ContextService
from engine.contracts.context_package import ContextPackage
from engine.contracts.stack_fingerprint import StackFingerprint
from engine.contracts.task import Task
from engine.contracts.task_signature import TaskSignature
from engine.contracts.vekl_activation_manifest import VEKLActivationManifest
from engine.contracts.vekl_manifest_invalidation import VEKLManifestInvalidation
from engine.contracts.vekl_resource import VEKLResource
from engine.contracts.vekl_resource_outcome import VEKLResourceOutcome
from engine.core.errors import DdeError
from engine.core.hashing import canonical_json, sha256_hex
from engine.core.ids import uuid7
from engine.donor.allowlist import assert_uri_admitted
from engine.donor.injection import screen_donor_text
from engine.studio.source.tables import (
    design_source_admissions,
    design_source_artifacts,
    design_sources,
)
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work
from engine.truth.tables import edrs, product_constitution_versions, requirements
from engine.vekl.compiler import VEKLContextCapsule, VEKLKnowledgeCompiler
from engine.vekl.engineering_playbook import (
    PACK_ID,
    PACK_REVISION,
    apply_engineering_playbook,
    resolve_required_skill_resources,
    skill_resource_specs,
)
from engine.vekl.models import (
    ActivationPlanSpec,
    ResourceOutcomeSpec,
    TaskSignatureSpec,
    VEKLResourceSpec,
)
from engine.vekl.policy import (
    EligibilityContext,
    enforce_target_scope,
    evaluate,
    rank_eligible,
)
from engine.vekl.repository import VEKLRepository
from engine.vekl.stack import StackObservation, observe_workspace_stack
from engine.vekl.tables import projects
from engine.workspaces.repository import WorkspaceRepository

LIFECYCLE_TRANSITIONS: dict[str, frozenset[str]] = {
    "DISCOVERED": frozenset({"METADATA_VERIFIED", "REVOKED"}),
    "METADATA_VERIFIED": frozenset({"REFERENCE_QUALIFIED", "REVOKED"}),
    "REFERENCE_QUALIFIED": frozenset(
        {"EXECUTION_QUARANTINED", "DEPRECATED", "REVOKED"}
    ),
    "EXECUTION_QUARANTINED": frozenset({"EXECUTION_EVALUATED", "REVOKED"}),
    "EXECUTION_EVALUATED": frozenset({"CANARY", "DEPRECATED", "REVOKED"}),
    "CANARY": frozenset({"PRODUCTION_QUALIFIED", "DEPRECATED", "REVOKED"}),
    "PRODUCTION_QUALIFIED": frozenset({"DEPRECATED", "REVOKED"}),
    "DEPRECATED": frozenset({"REVOKED"}),
    "REVOKED": frozenset(),
}
TOOL_KINDS = frozenset(
    {"TOOL", "CLI", "PLUGIN", "MCP_SERVER", "LSP_SERVER", "TEST_ORACLE"}
)
COMMUNITY_TRUST = frozenset(
    {"S5_MAINTAINER_COMMUNITY", "S6_COMMUNITY_CORROBORATED", "S7_DISCOVERY_ONLY"}
)


@dataclass(frozen=True)
class ProjectTruthSnapshot:
    project_kind: str
    truth_hash: str
    constraints: dict[str, object]
    refs: tuple[str, ...]


@dataclass(frozen=True)
class VEKLWorkerContext:
    """Worker-delivery binding: VEKL capsule plus the ordinary ContextPackage."""

    capsule: VEKLContextCapsule
    context_package: ContextPackage | ContextBudgetExceeded


class VEKLService:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        repository: VEKLRepository | None = None,
        compiler: VEKLKnowledgeCompiler | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or VEKLRepository()
        self._compiler = compiler or VEKLKnowledgeCompiler()

    async def _truth_snapshot(
        self, uow: PostgresUnitOfWork, *, tenant_id: UUID, project_id: UUID
    ) -> ProjectTruthSnapshot:
        project_row = (
            await uow.connection.execute(
                select(projects.c.kind).where(
                    projects.c.project_id == project_id,
                    projects.c.tenant_id == tenant_id,
                )
            )
        ).first()
        if project_row is None:
            raise DdeError("NOT_FOUND", "VEKL target project does not exist")
        kind = project_row[0]
        if kind not in {"TARGET_APPLICATION", "DDE_CONTROL_PLANE"}:
            raise DdeError(
                "VEKL_SCOPE_VIOLATION",
                "project kind is not classified for Production VEKL",
                details={"project_id": str(project_id)},
            )
        constitution_rows = (
            (
                await uow.connection.execute(
                    select(product_constitution_versions).where(
                        product_constitution_versions.c.project_id == project_id,
                        product_constitution_versions.c.status == "active",
                    )
                )
            )
            .mappings()
            .all()
        )
        requirement_rows = (
            (
                await uow.connection.execute(
                    select(requirements).where(
                        requirements.c.project_id == project_id,
                        requirements.c.status == "approved",
                    )
                )
            )
            .mappings()
            .all()
        )
        edr_rows = (
            (
                await uow.connection.execute(
                    select(edrs).where(
                        edrs.c.project_id == project_id,
                        edrs.c.status == "accepted",
                    )
                )
            )
            .mappings()
            .all()
        )
        constraints: dict[str, object] = {}
        refs: list[str] = []
        for row in sorted(constitution_rows, key=lambda item: item["version"]):
            key = f"constitution:{row['version']}"
            constraints[key] = row["content_hash"]
            refs.append(key)
        for row in sorted(requirement_rows, key=lambda item: item["slug"]):
            slug = str(row["slug"])
            constraints[f"requirement:{slug}"] = row["statement"]
            for index, value in enumerate(row["constraints"]):
                constraints[f"constraint:{slug}:{index}"] = value
            refs.append(f"requirement:{slug}")
        for row in sorted(edr_rows, key=lambda item: item["slug"]):
            key = f"edr:{row['slug']}"
            constraints[key] = row["decision"]
            refs.append(key)
        truth_hash = sha256_hex(
            canonical_json({"constraints": constraints, "refs": refs})
        )
        return ProjectTruthSnapshot(str(kind), truth_hash, constraints, tuple(refs))

    async def _validate_source_bridge(
        self,
        uow: PostgresUnitOfWork,
        *,
        tenant_id: UUID,
        project_id: UUID,
        spec: VEKLResourceSpec,
    ) -> dict[str, object]:
        provenance = dict(spec.provenance)
        if spec.source_uri is not None:
            if spec.source_id is None or spec.source_artifact_id is None:
                raise DdeError(
                    "VEKL_SOURCE_NOT_ADMITTED",
                    "external VEKL resources must bind an exact admitted Source "
                    "Intelligence artifact",
                )
            try:
                assert_uri_admitted(spec.source_uri)
            except DdeError as exc:
                raise DdeError(
                    "VEKL_SOURCE_NOT_ADMITTED",
                    "VEKL source host/path is not admitted by existing egress policy",
                    details={"source_uri": spec.source_uri},
                ) from exc
            provenance["egress_admitted"] = True
            provenance["egress_authority"] = "EDR-0015"
        if spec.source_id is not None:
            source = (
                (
                    await uow.connection.execute(
                        select(design_sources).where(
                            design_sources.c.source_id == spec.source_id,
                            design_sources.c.tenant_id == tenant_id,
                            design_sources.c.project_id == project_id,
                            design_sources.c.status == "AVAILABLE",
                        )
                    )
                )
                .mappings()
                .first()
            )
            if source is None:
                raise DdeError(
                    "VEKL_SOURCE_NOT_ADMITTED",
                    "Source Intelligence record is absent, scoped elsewhere or "
                    "unavailable",
                    details={"source_id": str(spec.source_id)},
                )
            provenance["source_record"] = str(spec.source_id)
        if spec.source_artifact_id is not None:
            artifact = (
                (
                    await uow.connection.execute(
                        select(design_source_artifacts).where(
                            design_source_artifacts.c.artifact_id
                            == spec.source_artifact_id,
                            design_source_artifacts.c.source_id == spec.source_id,
                            design_source_artifacts.c.project_id == project_id,
                        )
                    )
                )
                .mappings()
                .first()
            )
            if artifact is None or artifact["content_hash"] != spec.content_hash:
                raise DdeError(
                    "VEKL_SOURCE_NOT_ADMITTED",
                    "VEKL resource is not the exact Source Intelligence artifact "
                    "revision",
                )
            admitted = await uow.connection.scalar(
                select(design_source_admissions.c.admission_id).where(
                    design_source_admissions.c.artifact_id == spec.source_artifact_id,
                    design_source_admissions.c.project_id == project_id,
                    design_source_admissions.c.content_hash == spec.content_hash,
                    design_source_admissions.c.state == "ADMITTED",
                )
            )
            if admitted is None:
                raise DdeError(
                    "VEKL_SOURCE_NOT_ADMITTED",
                    "Source Intelligence artifact has no exact-content admission",
                )
            provenance["source_admission_id"] = str(admitted)
        return provenance

    async def _source_rejection_reason(
        self,
        uow: PostgresUnitOfWork,
        *,
        tenant_id: UUID,
        project_id: UUID,
        resource: VEKLResource,
    ) -> str | None:
        """Re-check current Source Intelligence + egress admission without fetching.

        Registration proves an exact admitted artifact for external URIs, but source
        status/admission or the accepted egress policy can later change.  Eligibility
        and context compilation therefore re-check the bridge before a resource may
        influence work.
        """
        if resource.source_uri is None and resource.source_id is None:
            return None
        if resource.source_uri is not None:
            if resource.source_id is None or resource.source_artifact_id is None:
                return "SOURCE_NOT_ADMITTED"
            try:
                assert_uri_admitted(resource.source_uri)
            except DdeError:
                return "SOURCE_NOT_ADMITTED"
        if resource.source_id is None:
            return "SOURCE_NOT_ADMITTED"
        source_id = await uow.connection.scalar(
            select(design_sources.c.source_id).where(
                design_sources.c.source_id == resource.source_id,
                design_sources.c.tenant_id == tenant_id,
                design_sources.c.project_id == project_id,
                design_sources.c.status == "AVAILABLE",
            )
        )
        if source_id is None:
            return "SOURCE_NOT_ADMITTED"
        if resource.source_artifact_id is None:
            return None
        artifact = (
            (
                await uow.connection.execute(
                    select(design_source_artifacts).where(
                        design_source_artifacts.c.artifact_id
                        == resource.source_artifact_id,
                        design_source_artifacts.c.source_id == resource.source_id,
                        design_source_artifacts.c.project_id == project_id,
                        design_source_artifacts.c.content_hash == resource.content_hash,
                    )
                )
            )
            .mappings()
            .first()
        )
        if artifact is None:
            return "SOURCE_ARTIFACT_CHANGED"
        admission = await uow.connection.scalar(
            select(design_source_admissions.c.admission_id).where(
                design_source_admissions.c.artifact_id == resource.source_artifact_id,
                design_source_admissions.c.project_id == project_id,
                design_source_admissions.c.content_hash == resource.content_hash,
                design_source_admissions.c.state == "ADMITTED",
            )
        )
        return None if admission is not None else "SOURCE_ADMISSION_REVOKED"

    async def register_resource(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        spec: VEKLResourceSpec,
        request_mode: str,
    ) -> VEKLResource:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            truth = await self._truth_snapshot(
                uow, tenant_id=tenant_id, project_id=project_id
            )
            enforce_target_scope(
                project_kind=truth.project_kind, request_mode=request_mode
            )
            provenance = await self._validate_source_bridge(
                uow, tenant_id=tenant_id, project_id=project_id, spec=spec
            )
            findings = screen_donor_text(spec.content_excerpt)
            now = datetime.now(UTC)
            resource = VEKLResource(
                resource_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                lifecycle_state="DISCOVERED",
                injection_findings=findings,
                provenance=provenance,
                created_at=now,
                updated_at=now,
                **spec.model_dump(exclude={"provenance"}),
            )
            await self._repository.insert_resource(uow.connection, resource)
            await uow.commit()
            return resource

    async def install_engineering_playbook_candidates(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        request_mode: str,
    ) -> dict[str, object]:
        """Register the DDE-owned engineering playbook Skills as candidates.

        Installation is deliberately candidate-only. It never promotes a Skill past
        ``DISCOVERED`` and therefore cannot make procedural guidance active without the
        ordinary VEKL qualification and ActivationManifest path. Repeated calls reuse
        exact pack revision/content hashes already present in the target project.
        """

        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            truth = await self._truth_snapshot(
                uow, tenant_id=tenant_id, project_id=project_id
            )
            enforce_target_scope(
                project_kind=truth.project_kind, request_mode=request_mode
            )
            existing = await self._repository.list_resources(
                uow.connection, project_id=project_id
            )
        by_content = {
            (item.content_hash, item.revision): item
            for item in existing
            if item.provenance.get("source") == PACK_ID
        }
        created: list[VEKLResource] = []
        reused: list[VEKLResource] = []
        for spec in skill_resource_specs():
            current = by_content.get((spec.content_hash, spec.revision))
            if current is not None:
                reused.append(current)
                continue
            created.append(
                await self.register_resource(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    spec=spec,
                    request_mode=request_mode,
                )
            )
        return {
            "pack_id": PACK_ID,
            "revision": PACK_REVISION,
            "qualification_state": "CANDIDATE_ONLY",
            "created": [item.model_dump(mode="json") for item in created],
            "reused": [item.model_dump(mode="json") for item in reused],
        }

    async def transition_resource(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        resource_id: UUID,
        to_state: str,
        request_mode: str,
    ) -> VEKLResource:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            truth = await self._truth_snapshot(
                uow, tenant_id=tenant_id, project_id=project_id
            )
            enforce_target_scope(
                project_kind=truth.project_kind, request_mode=request_mode
            )
            resource = await self._repository.get_resource(
                uow.connection, project_id=project_id, resource_id=resource_id
            )
            if resource is None:
                raise DdeError("NOT_FOUND", "VEKL resource not found")
            if to_state not in LIFECYCLE_TRANSITIONS[resource.lifecycle_state]:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "invalid VEKL qualification transition",
                    details={"from": resource.lifecycle_state, "to": to_state},
                )
            qualifying = to_state in {
                "REFERENCE_QUALIFIED",
                "EXECUTION_EVALUATED",
                "CANARY",
                "PRODUCTION_QUALIFIED",
            }
            if qualifying and resource.injection_findings:
                raise DdeError(
                    "POLICY_DENIED",
                    "prompt-injected external content cannot be qualified",
                    details={"findings": resource.injection_findings},
                )
            if qualifying:
                source_rejection = await self._source_rejection_reason(
                    uow,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    resource=resource,
                )
                if source_rejection is not None:
                    raise DdeError(
                        "VEKL_SOURCE_NOT_ADMITTED",
                        "VEKL source/artifact admission is no longer current",
                        details={
                            "resource_id": str(resource.resource_id),
                            "reason": source_rejection,
                        },
                    )
            await self._repository.transition_resource(
                uow.connection,
                project_id=project_id,
                resource_id=resource_id,
                lifecycle_state=to_state,
                updated_at=datetime.now(UTC),
            )
            updated = resource.model_copy(
                update={"lifecycle_state": to_state, "updated_at": datetime.now(UTC)}
            )
            await uow.commit()
            return updated

    async def _persist_stack_fingerprint(
        self,
        uow: PostgresUnitOfWork,
        *,
        tenant_id: UUID,
        project_id: UUID,
        truth: ProjectTruthSnapshot,
        observation: StackObservation,
    ) -> StackFingerprint:
        if not observation.evidence_refs:
            raise DdeError(
                "EVIDENCE_MISSING",
                "StackFingerprint requires mechanically observed workspace evidence",
            )
        payload = {
            "project_truth_hash": truth.truth_hash,
            "facts": observation.facts,
            "evidence_refs": list(observation.evidence_refs),
        }
        digest = sha256_hex(canonical_json(payload))
        existing = await self._repository.fingerprint_by_hash(
            uow.connection, project_id=project_id, fingerprint_hash=digest
        )
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        record = StackFingerprint(
            fingerprint_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            project_truth_hash=truth.truth_hash,
            facts=observation.facts,
            evidence_refs=list(observation.evidence_refs),
            fingerprint_hash=digest,
            created_at=now,
            updated_at=now,
        )
        await self._repository.insert_fingerprint(uow.connection, record)
        return record

    async def build_stack_fingerprint_from_workspace(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        workspace_id: UUID,
        request_mode: str,
    ) -> StackFingerprint:
        """Mechanically observe the existing DDE Workspace and persist its fingerprint.

        This is the production Gateway boundary. Caller/model-declared stack facts are
        intentionally not accepted; the Workspace row and content-hashed stack files
        are the evidence source.
        """
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            truth = await self._truth_snapshot(
                uow, tenant_id=tenant_id, project_id=project_id
            )
            enforce_target_scope(
                project_kind=truth.project_kind, request_mode=request_mode
            )
            workspace = await WorkspaceRepository().get_workspace(
                uow.connection, workspace_id
            )
            if (
                workspace is None
                or workspace.tenant_id != tenant_id
                or workspace.project_id != project_id
            ):
                raise DdeError(
                    "TENANT_SCOPE_VIOLATION",
                    "VEKL workspace is outside the addressed tenant/project",
                )
            observation = observe_workspace_stack(workspace)
            record = await self._persist_stack_fingerprint(
                uow,
                tenant_id=tenant_id,
                project_id=project_id,
                truth=truth,
                observation=observation,
            )
            await uow.commit()
            return record

    async def build_task_signature(
        self,
        *,
        task: Task,
        fingerprint: StackFingerprint,
        spec: TaskSignatureSpec,
    ) -> TaskSignature:
        if (
            task.project_id != fingerprint.project_id
            or task.tenant_id != fingerprint.tenant_id
        ):
            raise DdeError(
                "TENANT_SCOPE_VIOLATION", "fingerprint and task scope differ"
            )
        spec, _engineering_policy = apply_engineering_playbook(task, spec)
        versions = fingerprint.facts.get("versions", {})
        constraints = dict(spec.constraints)
        constraints["versions"] = versions if isinstance(versions, dict) else {}
        constraints["stack"] = dict(fingerprint.facts)
        constraints["requirement_refs"] = sorted(task.requirement_refs)
        constraints["feature_refs"] = sorted(task.feature_refs)
        payload = {
            "task_id": str(task.task_id),
            "fingerprint_hash": fingerprint.fingerprint_hash,
            "lifecycle_stage": spec.lifecycle_stage,
            "task_class": task.task_class,
            "constraints": constraints,
            "risk_category": task.risk_class,
            **spec.model_dump(
                exclude={"lifecycle_stage", "engineering_archetype", "constraints"}
            ),
        }
        digest = sha256_hex(canonical_json(payload))
        async with open_unit_of_work(
            self._engine, tenant_id=task.tenant_id, project_id=task.project_id
        ) as uow:
            existing = await self._repository.signature_by_hash(
                uow.connection, task_id=task.task_id, signature_hash=digest
            )
            if existing is not None:
                return existing
            now = datetime.now(UTC)
            record = TaskSignature(
                signature_id=uuid7(),
                tenant_id=task.tenant_id,
                project_id=task.project_id,
                task_id=task.task_id,
                fingerprint_id=fingerprint.fingerprint_id,
                lifecycle_stage=spec.lifecycle_stage,
                task_class=task.task_class,
                constraints=constraints,
                risk_category=task.risk_class,
                error_signatures=spec.error_signatures,
                required_capabilities=spec.required_capabilities,
                allowed_filesystem_scopes=spec.allowed_filesystem_scopes,
                allowed_network_scopes=spec.allowed_network_scopes,
                allowed_secret_scopes=spec.allowed_secret_scopes,
                required_verifiers=spec.required_verifiers,
                freshness_needs=spec.freshness_needs,
                budget=spec.budget,
                signature_hash=digest,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_signature(uow.connection, record)
            await uow.commit()
            return record

    async def _invalidate(
        self,
        uow: PostgresUnitOfWork,
        *,
        manifest: VEKLActivationManifest,
        code: str,
        detail: dict[str, object],
        policy_hash: str,
        truth_hash: str,
    ) -> None:
        existing = await self._repository.invalidations_for_manifest(
            uow.connection, manifest_id=manifest.manifest_id
        )
        if existing:
            return
        now = datetime.now(UTC)
        await self._repository.insert_invalidation(
            uow.connection,
            VEKLManifestInvalidation(
                invalidation_id=uuid7(),
                tenant_id=manifest.tenant_id,
                project_id=manifest.project_id,
                manifest_id=manifest.manifest_id,
                reason_code=code,
                detail=detail,
                observed_policy_hash=policy_hash,
                observed_truth_hash=truth_hash,
                created_at=now,
                updated_at=now,
            ),
        )

    async def plan_activation(
        self,
        *,
        task: Task,
        fingerprint: StackFingerprint,
        signature: TaskSignature,
        spec: ActivationPlanSpec,
    ) -> VEKLActivationManifest:
        if (
            task.task_id != signature.task_id
            or signature.fingerprint_id != fingerprint.fingerprint_id
        ):
            raise DdeError(
                "POLICY_DENIED", "VEKL execution identity binding is inconsistent"
            )
        policy_hash = sha256_hex(canonical_json(spec.policy))
        async with open_unit_of_work(
            self._engine, tenant_id=task.tenant_id, project_id=task.project_id
        ) as uow:
            truth = await self._truth_snapshot(
                uow, tenant_id=task.tenant_id, project_id=task.project_id
            )
            enforce_target_scope(
                project_kind=truth.project_kind, request_mode=spec.request_mode
            )
            prior = await self._repository.latest_manifest_for_attempt(
                uow.connection,
                project_id=task.project_id,
                task_id=task.task_id,
                task_attempt_id=spec.task_attempt_id,
            )
            if prior is not None:
                invalidations = await self._repository.invalidations_for_manifest(
                    uow.connection, manifest_id=prior.manifest_id
                )
                code = None
                detail: dict[str, object] = {}
                if invalidations:
                    code = "VEKL_MANIFEST_INVALID"
                elif prior.task_signature_id != signature.signature_id:
                    code, detail = (
                        "VEKL_TASK_SIGNATURE_CHANGED",
                        {
                            "expected": str(prior.task_signature_id),
                            "observed": str(signature.signature_id),
                        },
                    )
                elif prior.policy_hash != policy_hash:
                    code, detail = (
                        "VEKL_POLICY_CHANGED",
                        {"expected": prior.policy_hash, "observed": policy_hash},
                    )
                elif prior.project_truth_hash != truth.truth_hash:
                    code, detail = (
                        "VEKL_PROJECT_TRUTH_CHANGED",
                        {
                            "expected": prior.project_truth_hash,
                            "observed": truth.truth_hash,
                        },
                    )
                elif prior.stack_fingerprint_hash != fingerprint.fingerprint_hash:
                    code, detail = (
                        "VEKL_STACK_CHANGED",
                        {
                            "expected": prior.stack_fingerprint_hash,
                            "observed": fingerprint.fingerprint_hash,
                        },
                    )
                else:
                    for binding in prior.selected_resources:
                        current = await self._repository.get_resource(
                            uow.connection,
                            project_id=task.project_id,
                            resource_id=UUID(str(binding["resource_id"])),
                        )
                        source_rejection = (
                            None
                            if current is None
                            else await self._source_rejection_reason(
                                uow,
                                tenant_id=task.tenant_id,
                                project_id=task.project_id,
                                resource=current,
                            )
                        )
                        if (
                            current is None
                            or current.lifecycle_state == "REVOKED"
                            or current.revision != binding["revision"]
                            or current.content_hash != binding["content_hash"]
                            or source_rejection is not None
                        ):
                            code, detail = (
                                "VEKL_RESOURCE_CHANGED",
                                {
                                    "resource_id": str(binding["resource_id"]),
                                    "source_reason": source_rejection,
                                },
                            )
                            break
                if code is None:
                    return prior
                await self._invalidate(
                    uow,
                    manifest=prior,
                    code=code,
                    detail=detail,
                    policy_hash=policy_hash,
                    truth_hash=truth.truth_hash,
                )
                await uow.commit()
                raise DdeError(
                    "VEKL_MANIFEST_INVALID",
                    "existing activation manifest was invalidated; silent reselection "
                    "is forbidden",
                    details={"reason": code, **detail},
                )

            resources = await self._repository.list_resources(
                uow.connection, project_id=task.project_id
            )
            admitted_ids = frozenset(
                str(row[0])
                for row in (
                    await uow.connection.execute(
                        select(design_sources.c.source_id).where(
                            design_sources.c.project_id == task.project_id,
                            design_sources.c.status == "AVAILABLE",
                        )
                    )
                ).all()
            )
            context = EligibilityContext(
                project_kind=truth.project_kind,
                request_mode=spec.request_mode,
                truth_constraints=truth.constraints,
                admitted_source_ids=admitted_ids,
                available_capabilities=frozenset(spec.available_capabilities),
                available_verifiers=frozenset(spec.available_verifiers),
                sandbox_available=spec.sandbox_available,
                offline=spec.offline,
                now=datetime.now(UTC),
            )
            mandatory = set(spec.mandatory_resource_ids)
            mandatory.update(
                resolve_required_skill_resources(
                    signature_constraints=signature.constraints,
                    resources=resources,
                    requested_modes=spec.requested_modes,
                )
            )
            decisions = []
            rejected: dict[str, list[str]] = {}
            for resource in resources:
                source_rejection = await self._source_rejection_reason(
                    uow,
                    tenant_id=task.tenant_id,
                    project_id=task.project_id,
                    resource=resource,
                )
                if source_rejection is not None:
                    rejected[str(resource.resource_id)] = [source_rejection]
                    continue
                possible = [
                    mode
                    for mode in spec.requested_modes
                    if mode in resource.activation_modes
                ]
                if not possible:
                    if resource.resource_id in mandatory:
                        rejected[str(resource.resource_id)] = [
                            "ACTIVATION_MODE_UNQUALIFIED"
                        ]
                    continue
                decision = evaluate(
                    resource,
                    activation_mode=possible[0],
                    signature=signature,
                    context=context,
                )
                if decision.eligible:
                    decisions.append(decision)
                else:
                    rejected[str(resource.resource_id)] = list(decision.reasons)
            missing_mandatory = {
                str(resource_id): rejected.get(str(resource_id), ["RESOURCE_NOT_FOUND"])
                for resource_id in mandatory
                if all(item.resource.resource_id != resource_id for item in decisions)
            }
            if missing_mandatory:
                reasons = next(iter(missing_mandatory.values()))
                code = (
                    "BUDGET_EXCEEDED"
                    if "RESERVED_BUDGET_INSUFFICIENT" in reasons
                    else "VEKL_RESOURCE_INELIGIBLE"
                )
                raise DdeError(
                    code,
                    "mandatory VEKL resource failed hard eligibility",
                    details={"resources": missing_mandatory},
                )
            ranked = rank_eligible(decisions)
            selected = []
            selected_keys: set[str] = set()
            for decision in ranked:
                resource = decision.resource
                purpose = str(
                    resource.provenance.get("purpose") or decision.activation_mode
                )
                if resource.resource_id not in mandatory and purpose in selected_keys:
                    continue
                selected_keys.add(purpose)
                selected.append(
                    {
                        "resource_id": str(resource.resource_id),
                        "revision": resource.revision,
                        "content_hash": resource.content_hash,
                        "activation_mode": decision.activation_mode,
                        "reason": "mandatory"
                        if resource.resource_id in mandatory
                        else "highest_eligible_for_purpose",
                        "mandatory": resource.resource_id in mandatory,
                        "score": list(decision.score),
                    }
                )
            if not selected:
                raise DdeError(
                    "VEKL_RESOURCE_INELIGIBLE",
                    "no qualified VEKL resource is eligible for this task",
                    details={"rejections": rejected},
                )
            by_id = {str(resource.resource_id): resource for resource in resources}
            bound = [by_id[str(item["resource_id"])] for item in selected]
            tools = [
                item
                for item in selected
                if by_id[str(item["resource_id"])].resource_kind in TOOL_KINDS
            ]
            hooks = [
                item
                for item in selected
                if by_id[str(item["resource_id"])].resource_kind == "HOOK"
            ]
            loops = [
                item
                for item in selected
                if by_id[str(item["resource_id"])].resource_kind == "LOOP"
            ]
            community = [
                item
                for item in selected
                if by_id[str(item["resource_id"])].source_trust in COMMUNITY_TRUST
            ]
            freshness = {
                str(resource.resource_id): resource.freshness for resource in bound
            }
            manifest_payload = {
                "tenant_id": str(task.tenant_id),
                "project_id": str(task.project_id),
                "mission_id": str(task.mission_id),
                "task_id": str(task.task_id),
                "task_attempt_id": str(spec.task_attempt_id)
                if spec.task_attempt_id
                else None,
                "worker_run_id": str(spec.worker_run_id)
                if spec.worker_run_id
                else None,
                "task_signature_id": str(signature.signature_id),
                "stack_fingerprint_id": str(fingerprint.fingerprint_id),
                "project_truth_hash": truth.truth_hash,
                "stack_fingerprint_hash": fingerprint.fingerprint_hash,
                "policy_hash": policy_hash,
                "selected_resources": selected,
                "tools": tools,
                "hooks": hooks,
                "loops": loops,
                "community_evidence": community,
                "freshness_state": freshness,
            }
            digest = sha256_hex(canonical_json(manifest_payload))
            existing = await self._repository.manifest_by_hash(
                uow.connection, project_id=task.project_id, manifest_hash=digest
            )
            if existing is not None:
                return existing
            now = datetime.now(UTC)
            manifest = VEKLActivationManifest(
                manifest_id=uuid7(),
                created_at=now,
                updated_at=now,
                manifest_hash=digest,
                **manifest_payload,
            )
            await self._repository.insert_manifest(uow.connection, manifest)
            await uow.commit()
            return manifest

    @staticmethod
    def _task_relevant_truth(
        truth: ProjectTruthSnapshot, signature: TaskSignature
    ) -> dict[str, object]:
        """Keep global constitution/EDRs plus task-addressed requirement constraints.

        Requirement references are free-form canonical refs today.  When they do not
        map mechanically to the stored requirement keys we keep the full authoritative
        snapshot rather than guessing and silently dropping truth.
        """
        raw_refs = signature.constraints.get("requirement_refs", [])
        refs = {str(item) for item in raw_refs} if isinstance(raw_refs, list) else set()
        if not refs:
            return dict(truth.constraints)
        global_items = {
            key: value
            for key, value in truth.constraints.items()
            if key.startswith("constitution:") or key.startswith("edr:")
        }
        matched: dict[str, object] = {}
        for key, value in truth.constraints.items():
            if key.startswith("requirement:") or key.startswith("constraint:"):
                if any(ref == key or ref in key or key.endswith(ref) for ref in refs):
                    matched[key] = value
        if not matched:
            return dict(truth.constraints)
        return {**global_items, **matched}

    async def _validated_context_inputs(
        self,
        uow: PostgresUnitOfWork,
        *,
        tenant_id: UUID,
        project_id: UUID,
        manifest: VEKLActivationManifest,
    ) -> tuple[
        ProjectTruthSnapshot, list[VEKLResource], StackFingerprint, TaskSignature
    ]:
        persisted = await self._repository.get_manifest(
            uow.connection, project_id=project_id, manifest_id=manifest.manifest_id
        )
        if persisted is None or persisted.manifest_hash != manifest.manifest_hash:
            raise DdeError(
                "VEKL_MANIFEST_INVALID",
                "VEKL context requires the exact persisted activation manifest",
            )
        invalidations = await self._repository.invalidations_for_manifest(
            uow.connection, manifest_id=manifest.manifest_id
        )
        if invalidations:
            raise DdeError(
                "VEKL_MANIFEST_INVALID",
                "VEKL activation manifest is invalidated",
                details={"reason": invalidations[-1].reason_code},
            )
        truth = await self._truth_snapshot(
            uow, tenant_id=tenant_id, project_id=project_id
        )
        enforce_target_scope(
            project_kind=truth.project_kind,
            request_mode="APPLICATION_MANUFACTURING_VEKL",
        )
        fingerprint = await self._repository.get_fingerprint(
            uow.connection,
            project_id=project_id,
            fingerprint_id=manifest.stack_fingerprint_id,
        )
        signature = await self._repository.get_signature(
            uow.connection,
            project_id=project_id,
            signature_id=manifest.task_signature_id,
        )
        code: str | None = None
        detail: dict[str, object] = {}
        if truth.truth_hash != manifest.project_truth_hash:
            code = "VEKL_PROJECT_TRUTH_CHANGED"
            detail = {
                "expected": manifest.project_truth_hash,
                "observed": truth.truth_hash,
            }
        elif (
            fingerprint is None
            or fingerprint.fingerprint_hash != manifest.stack_fingerprint_hash
            or fingerprint.project_truth_hash != manifest.project_truth_hash
        ):
            code = "VEKL_STACK_CHANGED"
        elif (
            signature is None
            or signature.task_id != manifest.task_id
            or signature.fingerprint_id != manifest.stack_fingerprint_id
        ):
            code = "VEKL_TASK_SIGNATURE_CHANGED"
        resources = await self._repository.list_resources(
            uow.connection, project_id=project_id
        )
        by_id = {str(resource.resource_id): resource for resource in resources}
        if code is None:
            for binding in manifest.selected_resources:
                resource_id = str(binding.get("resource_id", ""))
                current = by_id.get(resource_id)
                source_rejection = (
                    None
                    if current is None
                    else await self._source_rejection_reason(
                        uow,
                        tenant_id=tenant_id,
                        project_id=project_id,
                        resource=current,
                    )
                )
                if (
                    current is None
                    or current.lifecycle_state == "REVOKED"
                    or current.revision != binding.get("revision")
                    or current.content_hash != binding.get("content_hash")
                    or source_rejection is not None
                ):
                    code = "VEKL_RESOURCE_CHANGED"
                    detail = {
                        "resource_id": resource_id,
                        "source_reason": source_rejection,
                    }
                    break
        if code is not None:
            await self._invalidate(
                uow,
                manifest=manifest,
                code=code,
                detail=detail,
                policy_hash=manifest.policy_hash,
                truth_hash=truth.truth_hash,
            )
            await uow.commit()
            raise DdeError(
                "VEKL_MANIFEST_INVALID",
                "VEKL activation manifest is no longer valid for context delivery",
                details={"reason": code, **detail},
            )
        if fingerprint is None or signature is None:
            raise DdeError(
                "VEKL_MANIFEST_INVALID",
                "validated VEKL manifest lost its stack/task binding",
            )
        return truth, resources, fingerprint, signature

    async def compile_context(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        manifest: VEKLActivationManifest,
        token_budget: int,
    ) -> VEKLContextCapsule:
        if manifest.tenant_id != tenant_id or manifest.project_id != project_id:
            raise DdeError("TENANT_SCOPE_VIOLATION", "VEKL manifest scope differs")
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            (
                truth,
                resources,
                fingerprint,
                signature,
            ) = await self._validated_context_inputs(
                uow,
                tenant_id=tenant_id,
                project_id=project_id,
                manifest=manifest,
            )
            relevant_truth = self._task_relevant_truth(truth, signature)
            engineering_policy = signature.constraints.get("engineering_playbook", {})
            if not isinstance(engineering_policy, dict):
                raise DdeError(
                    "VEKL_MANIFEST_INVALID",
                    "TaskSignature engineering playbook policy must be an object",
                )
        return self._compiler.compile(
            manifest=manifest,
            resources=resources,
            truth_constraints=relevant_truth,
            token_budget=token_budget,
            stack_facts=fingerprint.facts,
            task_verifiers=tuple(signature.required_verifiers),
            engineering_policy=engineering_policy,
        )

    async def get_manifest(
        self, *, tenant_id: UUID, project_id: UUID, manifest_id: UUID
    ) -> VEKLActivationManifest:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            manifest = await self._repository.get_manifest(
                uow.connection, project_id=project_id, manifest_id=manifest_id
            )
        if manifest is None:
            raise DdeError("NOT_FOUND", "VEKL activation manifest not found")
        return manifest

    async def compile_worker_context(
        self,
        *,
        task: Task,
        manifest: VEKLActivationManifest,
        context_budget_tokens: int,
    ) -> VEKLWorkerContext:
        """Bind VEKL into the existing ContextService budget/package authority."""
        if (
            task.tenant_id != manifest.tenant_id
            or task.project_id != manifest.project_id
            or task.task_id != manifest.task_id
            or task.mission_id != manifest.mission_id
        ):
            raise DdeError(
                "TENANT_SCOPE_VIOLATION",
                "VEKL manifest and worker-context task identity differ",
            )
        async with open_unit_of_work(
            self._engine, tenant_id=task.tenant_id, project_id=task.project_id
        ) as uow:
            signature = await self._repository.get_signature(
                uow.connection,
                project_id=task.project_id,
                signature_id=manifest.task_signature_id,
            )
            if signature is None:
                raise DdeError("VEKL_MANIFEST_INVALID", "task signature is missing")
        reserved = signature.budget.get("tokens", context_budget_tokens)
        if not isinstance(reserved, int) or isinstance(reserved, bool) or reserved < 1:
            raise DdeError(
                "BUDGET_EXCEEDED",
                "TaskSignature must reserve a positive VEKL token budget",
            )
        capsule = await self.compile_context(
            tenant_id=task.tenant_id,
            project_id=task.project_id,
            manifest=manifest,
            token_budget=min(context_budget_tokens, reserved),
        )
        extension = ContextExtension(
            name="vekl",
            content_hash=capsule.capsule_hash,
            token_estimate=capsule.estimated_tokens,
            provenance_refs=capsule.provenance_refs,
        )
        context_package = await ContextService(self._engine).compile(
            task=task,
            context_budget_tokens=context_budget_tokens,
            extensions=(extension,),
        )
        return VEKLWorkerContext(capsule=capsule, context_package=context_package)

    async def record_outcome(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        manifest_id: UUID,
        spec: ResourceOutcomeSpec,
    ) -> VEKLResourceOutcome:
        if not spec.verifier_refs or not spec.evidence_refs:
            raise DdeError(
                "EVIDENCE_MISSING",
                "VEKL resource outcomes require verifier and evidence refs",
            )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            manifests = await self._repository.list_manifests(
                uow.connection, project_id=project_id
            )
            manifest = next(
                (item for item in manifests if item.manifest_id == manifest_id), None
            )
            if manifest is None:
                raise DdeError("NOT_FOUND", "VEKL activation manifest not found")
            now = datetime.now(UTC)
            record = VEKLResourceOutcome(
                outcome_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                manifest_id=manifest_id,
                resource_revisions=[
                    {
                        key: item[key]
                        for key in ("resource_id", "revision", "content_hash")
                    }
                    for item in manifest.selected_resources
                ],
                created_at=now,
                updated_at=now,
                **spec.model_dump(),
            )
            await self._repository.insert_outcome(uow.connection, record)
            await uow.commit()
            return record

    async def projection(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> dict[str, object]:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            resources = await self._repository.list_resources(
                uow.connection, project_id=project_id
            )
            manifests = await self._repository.list_manifests(
                uow.connection, project_id=project_id
            )
            outcomes = await self._repository.list_outcomes(
                uow.connection, project_id=project_id
            )
            invalidations = []
            for manifest in manifests:
                invalidations.extend(
                    await self._repository.invalidations_for_manifest(
                        uow.connection, manifest_id=manifest.manifest_id
                    )
                )
        active_ids = {
            str(binding["resource_id"])
            for manifest in manifests
            if all(item.manifest_id != manifest.manifest_id for item in invalidations)
            for binding in manifest.selected_resources
        }
        active = [
            resource
            for resource in resources
            if str(resource.resource_id) in active_ids
        ]
        sections = {
            "stack_map": [],
            "knowledge": [],
            "tools_plugins_mcp": [],
            "rules_hooks": [],
            "loops": [],
            "community_evidence": [],
            "security": [],
            "learning": [item.model_dump(mode="json") for item in outcomes],
        }
        for resource in active:
            row = resource.model_dump(mode="json")
            sections["security"].append(row)
            if resource.resource_kind in TOOL_KINDS:
                sections["tools_plugins_mcp"].append(row)
            elif (
                resource.resource_kind == "HOOK"
                or resource.resource_kind == "RULE_PACK"
            ):
                sections["rules_hooks"].append(row)
            elif resource.resource_kind == "LOOP":
                sections["loops"].append(row)
            elif resource.source_trust in COMMUNITY_TRUST:
                sections["community_evidence"].append(row)
            else:
                sections["knowledge"].append(row)
        return {
            "availability": "AVAILABLE" if resources else "EMPTY",
            "sections": sections,
            "resources": [item.model_dump(mode="json") for item in resources],
            "manifests": [item.model_dump(mode="json") for item in manifests],
            "invalidations": [item.model_dump(mode="json") for item in invalidations],
        }

    @staticmethod
    def hermes_candidate(payload: dict[str, object]) -> dict[str, object]:
        """Return advisory data without a write path into VEKL authority."""
        return {"authority": "CANDIDATE_ONLY", "payload": payload}
