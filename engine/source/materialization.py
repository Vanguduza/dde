"""Materialize quarantined workflow snapshots into sanitized descriptors.

Raw n8n workflow bytes remain project-scoped Source Intelligence artifacts and
never become VEKL context.  Only deterministic descriptors produced by the
pure parser/scanner in :mod:`engine.source.automation` are admitted for later
VEKL qualification.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.automation_pattern_descriptor import AutomationPatternDescriptor
from engine.contracts.automation_workflow_artifact import AutomationWorkflowArtifact
from engine.contracts.source_admission import SourceAdmission
from engine.contracts.source_artifact import SourceArtifact
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.object_store.durable import ScopedObjectStore, scoped_object_store_from_env
from engine.source.automation import (
    MAX_COMPRESSED_BYTES,
    PARSER_VERSION,
    SANITIZER_VERSION,
    SCANNER_VERSION,
    TOPOLOGY_COMPILER_VERSION,
    analyze_archive,
)
from engine.source.repository import SourceRepository
from engine.source.service import SourceService
from engine.truth.db import open_unit_of_work

RAW_COMPILER_VERSION = "dde-automation-raw-workflow-v2"
RAW_ADMISSION_POLICY_VERSION = "dde-automation-raw-quarantine-v2"
DESCRIPTOR_COMPILER_VERSION = "dde-automation-pattern-descriptor-v2"
DESCRIPTOR_ADMISSION_POLICY_VERSION = "dde-automation-pattern-admission-v2"


@dataclass(frozen=True)
class MaterializationResult:
    snapshot_id: UUID
    processed_workflows: int
    sanitized_workflows: int
    blocked_workflows: int
    rejected_workflows: int
    descriptor_count: int
    positive_descriptors: int
    anti_pattern_descriptors: int
    observation_descriptors: int


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()


def _raw_admission_state(state: str) -> str:
    if state == "BLOCKED":
        return "BLOCKED"
    if state == "REJECTED":
        return "REJECTED"
    return "QUARANTINED"


class AutomationCorpusMaterializationService:
    """Persist raw quarantine evidence and immutable sanitized descriptors."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        repository: SourceRepository | None = None,
        sources: SourceService | None = None,
        object_store: ScopedObjectStore | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or SourceRepository()
        self._sources = sources or SourceService(engine)
        self._objects = object_store or scoped_object_store_from_env(
            namespace="automation-corpus"
        )

    async def materialize_snapshot(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        snapshot_id: UUID,
        workflow_limit: int | None = None,
    ) -> MaterializationResult:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            snapshot = await self._repository.get_snapshot(
                uow.connection,
                snapshot_id=snapshot_id,
            )
        if snapshot is None:
            raise DdeError("CONTEXT_INCOMPLETE", "automation corpus snapshot is missing")
        if snapshot.state in {"REJECTED", "REVOKED"}:
            raise DdeError(
                "POLICY_DENIED",
                "rejected or revoked automation corpus snapshots cannot be materialized",
                retryable=False,
                details={"snapshot_id": str(snapshot.snapshot_id), "state": snapshot.state},
            )
        if snapshot.license_state != "VERIFIED":
            raise DdeError(
                "POLICY_DENIED",
                "automation corpus license must be verified before materialization",
                retryable=False,
            )
        archive = self._objects.read(
            tenant_id=tenant_id,
            project_id=project_id,
            key=snapshot.object_ref,
            max_bytes=MAX_COMPRESSED_BYTES,
        )
        actual_hash = sha256(archive).hexdigest()
        if actual_hash != snapshot.archive_sha256:
            raise DdeError(
                "VERSION_CONFLICT",
                "stored automation corpus bytes no longer match snapshot provenance",
                retryable=False,
                details={
                    "expected": snapshot.archive_sha256,
                    "actual": actual_hash,
                },
            )
        rows, _expanded = analyze_archive(archive, workflow_limit=workflow_limit)

        descriptor_count = 0
        positive = 0
        anti = 0
        observation = 0
        sanitized = 0
        blocked = 0
        rejected = 0
        for row in rows:
            workflow = await self._persist_raw_workflow(
                snapshot=snapshot,
                row=row,
            )
            state = str(row["state"])
            if state == "SANITIZED":
                sanitized += 1
            elif state == "BLOCKED":
                blocked += 1
            elif state == "REJECTED":
                rejected += 1
            if state != "SANITIZED":
                continue
            descriptor = await self._persist_descriptor(
                snapshot=snapshot,
                workflow=workflow,
                row=row,
            )
            descriptor_count += 1
            if descriptor.guidance_polarity == "POSITIVE":
                positive += 1
            elif descriptor.guidance_polarity == "ANTI_PATTERN":
                anti += 1
            else:
                observation += 1

        return MaterializationResult(
            snapshot_id=snapshot.snapshot_id,
            processed_workflows=len(rows),
            sanitized_workflows=sanitized,
            blocked_workflows=blocked,
            rejected_workflows=rejected,
            descriptor_count=descriptor_count,
            positive_descriptors=positive,
            anti_pattern_descriptors=anti,
            observation_descriptors=observation,
        )

    async def _persist_raw_workflow(
        self,
        *,
        snapshot: Any,
        row: dict[str, Any],
    ) -> AutomationWorkflowArtifact:
        raw = row["raw"]
        if not isinstance(raw, bytes):
            raise DdeError("VERSION_CONFLICT", "workflow analyzer did not return raw bytes")
        raw_hash = str(row["raw_hash"])
        object_ref = self._objects.put(
            tenant_id=snapshot.tenant_id,
            project_id=snapshot.project_id,
            content_hash=raw_hash,
            content=raw,
        )
        now = datetime.now(UTC)
        artifact = await self._sources.register_artifact(
            SourceArtifact(
                artifact_id=uuid7(),
                source_id=snapshot.source_id,
                tenant_id=snapshot.tenant_id,
                project_id=snapshot.project_id,
                parent_artifact_id=snapshot.artifact_id,
                artifact_kind="RAW_AUTOMATION_WORKFLOW",
                provider_artifact_key=(
                    f"{snapshot.repository}@{snapshot.commit_sha}:{row['path']}"
                ),
                title=str(row["path"]),
                source_uri=None,
                revision=snapshot.commit_sha,
                content_hash=raw_hash,
                content_object_ref=object_ref,
                content_object_backend=self._objects.backend_name,
                content_size_bytes=int(row["raw_size_bytes"]),
                media_type="application/json",
                metadata={
                    "path": str(row["path"]),
                    "parser_state": str(row["parser_state"]),
                    "workflow_state": str(row["state"]),
                },
                provenance={
                    "snapshot_id": str(snapshot.snapshot_id),
                    "snapshot_hash": snapshot.archive_sha256,
                    "raw_never_worker_context": True,
                },
                created_at=now,
                updated_at=now,
            )
        )
        raw_state = _raw_admission_state(str(row["state"]))
        findings = [str(value) for value in row.get("findings", [])]
        await self._sources.admit_artifact(
            SourceAdmission(
                admission_id=uuid7(),
                source_id=snapshot.source_id,
                artifact_id=artifact.artifact_id,
                tenant_id=snapshot.tenant_id,
                project_id=snapshot.project_id,
                content_hash=raw_hash,
                compiler_version=RAW_COMPILER_VERSION,
                policy_version=RAW_ADMISSION_POLICY_VERSION,
                qualification_domain="WORKFLOW_AUTOMATION",
                qualification_profile="RAW_WORKFLOW_QUARANTINE",
                state=raw_state,
                source_trust="S4_MAINTAINED_OSS",
                reuse_class=(
                    "SOURCE_REFERENCE_ONLY"
                    if raw_state == "QUARANTINED"
                    else "REJECTED"
                ),
                analysis={
                    "path": str(row["path"]),
                    "parser_state": str(row["parser_state"]),
                    "findings": findings,
                },
                hard_failures=(
                    findings if raw_state in {"BLOCKED", "REJECTED"} else []
                ),
                validation_obligations=[
                    "RAW_WORKFLOW_MUST_NEVER_ENTER_WORKER_CONTEXT",
                    "ONLY_SANITIZED_DESCRIPTOR_MAY_ENTER_VEKL",
                ],
                provenance={
                    "snapshot_id": str(snapshot.snapshot_id),
                    "raw_object_ref": object_ref,
                },
                security_state="QUARANTINED",
                license_state="VERIFIED",
                provenance_state="VERIFIED",
                sanitization_state=(
                    "DESCRIPTOR_READY" if raw_state == "QUARANTINED" else "BLOCKED"
                ),
                injection_state=(
                    "DETECTED"
                    if "PROMPT_INJECTION_TEXT" in findings
                    else "UNSCANNED_RAW"
                ),
                revoked_at=None,
                created_at=now,
                updated_at=now,
            )
        )
        record = AutomationWorkflowArtifact(
            workflow_artifact_id=uuid7(),
            tenant_id=snapshot.tenant_id,
            project_id=snapshot.project_id,
            snapshot_id=snapshot.snapshot_id,
            artifact_id=artifact.artifact_id,
            path=str(row["path"]),
            raw_hash=raw_hash,
            raw_size_bytes=int(row["raw_size_bytes"]),
            parser_state=str(row["parser_state"]),
            source_metadata=dict(row.get("source_metadata") or {}),
            state=str(row["state"]),
            findings=findings,
            pattern_lineage_id=(
                str(row["pattern_lineage_id"])
                if row.get("pattern_lineage_id") is not None
                else None
            ),
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            self._engine,
            tenant_id=snapshot.tenant_id,
            project_id=snapshot.project_id,
        ) as uow:
            saved = await self._repository.insert_workflow(uow.connection, record)
            await uow.commit()
        return saved

    async def _persist_descriptor(
        self,
        *,
        snapshot: Any,
        workflow: AutomationWorkflowArtifact,
        row: dict[str, Any],
    ) -> AutomationPatternDescriptor:
        descriptor_payload = {
            key: row[key]
            for key in (
                "pattern_lineage_id",
                "pattern_revision_hash",
                "archetype",
                "guidance_polarity",
                "title",
                "summary",
                "trigger_classes",
                "action_classes",
                "integration_classes",
                "control_flow",
                "resilience_controls",
                "security_controls",
                "observability_controls",
                "failure_modes",
                "required_capabilities",
                "stack_constraints",
                "topology_hash",
                "topology_compiler_version",
                "security_findings",
                "pii_findings",
                "secret_findings",
                "prompt_findings",
                "implementation_guidance",
                "anti_pattern_notes",
                "auth_pattern",
                "retry_error_pattern",
                "idempotency_pattern",
                "persistence_pattern",
                "worker_safe_capsule",
                "parser_version",
                "sanitizer_version",
                "scanner_version",
                "descriptor_hash",
            )
        }
        descriptor_bytes = _canonical_json(descriptor_payload)
        descriptor_hash = str(row["descriptor_hash"])
        if sha256(_canonical_json({k: v for k, v in descriptor_payload.items() if k != "descriptor_hash"})).hexdigest() != descriptor_hash:
            raise DdeError(
                "VERSION_CONFLICT",
                "descriptor hash no longer matches sanitized descriptor payload",
                retryable=False,
            )
        object_hash = sha256(descriptor_bytes).hexdigest()
        object_ref = self._objects.put(
            tenant_id=snapshot.tenant_id,
            project_id=snapshot.project_id,
            content_hash=object_hash,
            content=descriptor_bytes,
        )
        now = datetime.now(UTC)
        artifact = await self._sources.register_artifact(
            SourceArtifact(
                artifact_id=uuid7(),
                source_id=snapshot.source_id,
                tenant_id=snapshot.tenant_id,
                project_id=snapshot.project_id,
                parent_artifact_id=workflow.artifact_id,
                artifact_kind="AUTOMATION_PATTERN_DESCRIPTOR",
                provider_artifact_key=(
                    f"descriptor:{row['pattern_lineage_id']}:{row['pattern_revision_hash']}"
                ),
                title=str(row["title"]),
                source_uri=None,
                revision=str(row["pattern_revision_hash"]),
                content_hash=descriptor_hash,
                content_object_ref=object_ref,
                content_object_backend=self._objects.backend_name,
                content_size_bytes=len(descriptor_bytes),
                media_type="application/vnd.dde.automation-pattern+json",
                metadata={
                    "guidance_polarity": str(row["guidance_polarity"]),
                    "archetype": str(row["archetype"]),
                },
                provenance={
                    "snapshot_id": str(snapshot.snapshot_id),
                    "workflow_artifact_id": str(workflow.workflow_artifact_id),
                    "raw_hash": workflow.raw_hash,
                    "parser_version": PARSER_VERSION,
                    "sanitizer_version": SANITIZER_VERSION,
                    "scanner_version": SCANNER_VERSION,
                    "topology_compiler_version": TOPOLOGY_COMPILER_VERSION,
                },
                created_at=now,
                updated_at=now,
            )
        )
        findings = [str(value) for value in row.get("findings", [])]
        await self._sources.admit_artifact(
            SourceAdmission(
                admission_id=uuid7(),
                source_id=snapshot.source_id,
                artifact_id=artifact.artifact_id,
                tenant_id=snapshot.tenant_id,
                project_id=snapshot.project_id,
                content_hash=descriptor_hash,
                compiler_version=DESCRIPTOR_COMPILER_VERSION,
                policy_version=DESCRIPTOR_ADMISSION_POLICY_VERSION,
                qualification_domain="WORKFLOW_AUTOMATION",
                qualification_profile="SANITIZED_PATTERN_DESCRIPTOR",
                state="ADMITTED",
                source_trust="S4_MAINTAINED_OSS",
                reuse_class="SOURCE_REFERENCE_ONLY",
                analysis={
                    "guidance_polarity": str(row["guidance_polarity"]),
                    "archetype": str(row["archetype"]),
                    "findings": findings,
                },
                hard_failures=[],
                validation_obligations=[
                    "VEKL_HARD_ELIGIBILITY_REQUIRED",
                    "GUIDANCE_POLARITY_MUST_BE_PRESERVED",
                ],
                provenance={
                    "snapshot_id": str(snapshot.snapshot_id),
                    "workflow_artifact_id": str(workflow.workflow_artifact_id),
                    "descriptor_object_ref": object_ref,
                },
                security_state="SANITIZED",
                license_state="VERIFIED",
                provenance_state="VERIFIED",
                sanitization_state="PASSED",
                injection_state=(
                    "SANITIZED"
                    if row.get("prompt_findings")
                    else "NO_INJECTION_TEXT"
                ),
                revoked_at=None,
                created_at=now,
                updated_at=now,
            )
        )
        descriptor = AutomationPatternDescriptor(
            descriptor_id=uuid7(),
            tenant_id=snapshot.tenant_id,
            project_id=snapshot.project_id,
            snapshot_id=snapshot.snapshot_id,
            artifact_id=artifact.artifact_id,
            pattern_lineage_id=str(row["pattern_lineage_id"]),
            pattern_revision_hash=str(row["pattern_revision_hash"]),
            archetype=str(row["archetype"]),
            guidance_polarity=str(row["guidance_polarity"]),
            title=str(row["title"]),
            summary=str(row["summary"]),
            trigger_classes=list(row["trigger_classes"]),
            action_classes=list(row["action_classes"]),
            integration_classes=list(row["integration_classes"]),
            control_flow=dict(row["control_flow"]),
            resilience_controls=list(row["resilience_controls"]),
            security_controls=list(row["security_controls"]),
            observability_controls=list(row["observability_controls"]),
            failure_modes=list(row["failure_modes"]),
            required_capabilities=list(row["required_capabilities"]),
            stack_constraints=dict(row["stack_constraints"]),
            source_workflow_refs=[str(workflow.workflow_artifact_id)],
            source_workflow_hashes=[workflow.raw_hash],
            parser_version=str(row["parser_version"]),
            sanitizer_version=str(row["sanitizer_version"]),
            scanner_version=str(row["scanner_version"]),
            descriptor_hash=descriptor_hash,
            topology_hash=str(row["topology_hash"]),
            topology_compiler_version=str(row["topology_compiler_version"]),
            security_findings=list(row["security_findings"]),
            pii_findings=list(row["pii_findings"]),
            secret_findings=list(row["secret_findings"]),
            prompt_findings=list(row["prompt_findings"]),
            implementation_guidance=list(row["implementation_guidance"]),
            anti_pattern_notes=list(row["anti_pattern_notes"]),
            auth_pattern=dict(row["auth_pattern"]),
            retry_error_pattern=dict(row["retry_error_pattern"]),
            idempotency_pattern=dict(row["idempotency_pattern"]),
            persistence_pattern=dict(row["persistence_pattern"]),
            worker_safe_capsule=dict(row["worker_safe_capsule"]),
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            self._engine,
            tenant_id=snapshot.tenant_id,
            project_id=snapshot.project_id,
        ) as uow:
            saved = await self._repository.insert_descriptor(uow.connection, descriptor)
            await uow.commit()
        return saved
