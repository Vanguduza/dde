"""Domain-neutral Source Intelligence service introduced by EDR-0018."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.design_source import DesignSource
from engine.contracts.design_source_admission import DesignSourceAdmission
from engine.contracts.design_source_artifact import DesignSourceArtifact
from engine.contracts.source_admission import SourceAdmission
from engine.contracts.source_artifact import SourceArtifact
from engine.contracts.source_record import SourceRecord
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.source.repository import SourceRepository
from engine.truth.db import open_unit_of_work

SOURCE_INTELLIGENCE_POLICY_VERSION = "dde-source-intelligence-v2"
DESIGN_BRIDGE_POLICY_VERSION = "dde-design-source-bridge-v2"


def _design_trust(source: DesignSource) -> str:
    if source.source_class in {"PROJECT_NATIVE", "DDE_LIBRARY", "ORGANISATION_LIBRARY"}:
        return "S2_FIRST_PARTY"
    if source.source_class in {"EXTERNAL_REGISTRY", "MOBILE_REGISTRY", "FIGMA"}:
        return "S3_VERIFIED_REGISTRY"
    if source.source_class == "DONOR":
        return "S7_DISCOVERY_ONLY"
    return "S8_UNTRUSTED"


def _design_status(status: str) -> str:
    if status in {
        "AVAILABLE",
        "DEGRADED",
        "NOT_CONFIGURED",
        "UNAVAILABLE",
        "BLOCKED",
        "DISABLED",
    }:
        return status
    return "BLOCKED"


def _design_reuse(license_state: object) -> str:
    return {
        "OPEN_REUSE": "OPEN_REUSE",
        "CONDITIONAL_REUSE": "CONDITIONAL_REUSE",
        "REFERENCE_ONLY": "REFERENCE_ONLY",
        "REJECTED": "REJECTED",
    }.get(str(license_state), "UNKNOWN")


class SourceService:
    def __init__(
        self, engine: AsyncEngine, *, repository: SourceRepository | None = None
    ) -> None:
        self._engine = engine
        self._repository = repository or SourceRepository()

    async def ensure_source(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        provider_key: str,
        display_name: str,
        source_domain: str,
        source_class: str,
        source_kind: str,
        source_trust: str,
        status: str = "AVAILABLE",
        policy_revision: str = SOURCE_INTELLIGENCE_POLICY_VERSION,
        config: dict[str, object] | None = None,
        source_id: UUID | None = None,
    ) -> SourceRecord:
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            existing = await self._repository.get_source_by_key(
                uow.connection, project_id=project_id, provider_key=provider_key
            )
            payload = {
                "source_id": existing.source_id if existing else source_id or uuid7(),
                "tenant_id": tenant_id,
                "project_id": project_id,
                "provider_key": provider_key,
                "display_name": display_name,
                "source_domain": source_domain,
                "source_class": source_class,
                "source_kind": source_kind,
                "source_trust": source_trust,
                "status": status,
                "policy_revision": policy_revision,
                "config": config or {},
                "revoked_at": existing.revoked_at if existing else None,
                "created_at": existing.created_at if existing else now,
                "updated_at": now,
            }
            record = SourceRecord.model_validate(payload)
            saved = await self._repository.upsert_source(uow.connection, record)
            await uow.commit()
            return saved

    async def register_artifact(self, record: SourceArtifact) -> SourceArtifact:
        async with open_unit_of_work(
            self._engine, tenant_id=record.tenant_id, project_id=record.project_id
        ) as uow:
            source = await self._repository.get_source(
                uow.connection, source_id=record.source_id
            )
            if source is None or source.status == "REVOKED":
                raise DdeError(
                    "POLICY_DENIED",
                    "source artifact registration requires an active source",
                    retryable=False,
                    details={"source_id": str(record.source_id)},
                )
            saved = await self._repository.insert_artifact(uow.connection, record)
            await uow.commit()
            return saved

    async def admit_artifact(self, record: SourceAdmission) -> SourceAdmission:
        async with open_unit_of_work(
            self._engine, tenant_id=record.tenant_id, project_id=record.project_id
        ) as uow:
            artifact = await self._repository.get_artifact(
                uow.connection, artifact_id=record.artifact_id
            )
            if artifact is None or artifact.content_hash != record.content_hash:
                raise DdeError(
                    "VALIDATION_FAILED",
                    "source admission must bind the exact stored artifact content",
                    retryable=False,
                    details={"artifact_id": str(record.artifact_id)},
                )
            saved = await self._repository.insert_admission(uow.connection, record)
            await uow.commit()
            return saved

    async def mirror_design_source(
        self,
        *,
        source: DesignSource,
        artifact: DesignSourceArtifact | None = None,
        admission: DesignSourceAdmission | None = None,
    ) -> tuple[SourceRecord, SourceArtifact | None, SourceAdmission | None]:
        neutral_source = await self.ensure_source(
            tenant_id=source.tenant_id,
            project_id=source.project_id,
            provider_key=source.provider_key,
            display_name=source.display_name,
            source_domain="DESIGN",
            source_class=source.source_class,
            source_kind=source.adapter_kind,
            source_trust=_design_trust(source),
            status=_design_status(source.status),
            policy_revision=DESIGN_BRIDGE_POLICY_VERSION,
            config={"design_source_id": str(source.source_id)},
            source_id=source.source_id,
        )
        neutral_artifact: SourceArtifact | None = None
        neutral_admission: SourceAdmission | None = None
        if artifact is not None:
            content_hash = artifact.content_hash or f"UNHASHED:{artifact.artifact_id}"
            neutral_artifact = SourceArtifact.model_validate(
                {
                    "artifact_id": artifact.artifact_id,
                    "source_id": neutral_source.source_id,
                    "tenant_id": artifact.tenant_id,
                    "project_id": artifact.project_id,
                    "parent_artifact_id": None,
                    "artifact_kind": f"DESIGN_{artifact.artifact_kind}",
                    "provider_artifact_key": artifact.provider_artifact_key,
                    "title": artifact.title,
                    "source_uri": artifact.source_uri,
                    "revision": artifact.version_ref or "UNVERSIONED",
                    "content_hash": content_hash,
                    "content_object_ref": artifact.content_object_ref,
                    "content_object_backend": artifact.content_object_backend,
                    "content_size_bytes": artifact.content_size_bytes,
                    "media_type": None,
                    "metadata": artifact.metadata,
                    "provenance": {
                        "bridge": DESIGN_BRIDGE_POLICY_VERSION,
                        "design_retrieval_state": artifact.retrieval_state,
                        "design_license_state": artifact.license_state,
                    },
                    "created_at": artifact.created_at,
                    "updated_at": artifact.updated_at,
                }
            )
            neutral_artifact = await self.register_artifact(neutral_artifact)
        if admission is not None:
            if neutral_artifact is None:
                raise DdeError(
                    "VALIDATION_FAILED",
                    "design admission bridge requires its exact mirrored artifact",
                    retryable=False,
                    details={"admission_id": str(admission.admission_id)},
                )
            neutral_admission = SourceAdmission.model_validate(
                {
                    "admission_id": admission.admission_id,
                    "source_id": neutral_source.source_id,
                    "artifact_id": neutral_artifact.artifact_id,
                    "tenant_id": admission.tenant_id,
                    "project_id": admission.project_id,
                    "content_hash": admission.content_hash,
                    "compiler_version": admission.compiler_version,
                    "policy_version": DESIGN_BRIDGE_POLICY_VERSION,
                    "qualification_domain": "DESIGN_SYSTEM",
                    "qualification_profile": "DESIGN_SYSTEM",
                    "state": admission.state,
                    "source_trust": neutral_source.source_trust,
                    "reuse_class": _design_reuse(
                        neutral_artifact.provenance.get(
                            "design_license_state", "UNKNOWN"
                        )
                    ),
                    "analysis": {
                        "framework_state": admission.framework_state,
                        "dependency_state": admission.dependency_state,
                        "accessibility_state": admission.accessibility_state,
                        "design_system_state": admission.design_system_state,
                        "token_mapping_report": admission.token_mapping_report,
                        "unsupported_behaviors": admission.unsupported_behaviors,
                    },
                    "hard_failures": admission.hard_failures,
                    "validation_obligations": admission.validation_obligations,
                    "provenance": {"bridge": DESIGN_BRIDGE_POLICY_VERSION},
                    "security_state": admission.security_state,
                    "license_state": admission.license_state,
                    "provenance_state": "VERIFIED",
                    "sanitization_state": "DESIGN_COMPILER",
                    "injection_state": "UNKNOWN",
                    "revoked_at": None,
                    "created_at": admission.created_at,
                    "updated_at": admission.updated_at,
                }
            )
            neutral_admission = await self.admit_artifact(neutral_admission)
        return neutral_source, neutral_artifact, neutral_admission
