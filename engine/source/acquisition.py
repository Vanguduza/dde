"""Governed exact-SHA acquisition for the EDR-0018 automation corpus.

This is the only production network path for Zie619/n8n-workflows.  It is
lease-bound, journaled before network I/O, redirect-free, anonymously fetched,
strictly size-bounded, project-scoped in durable object storage, and persisted
as quarantined Source Intelligence evidence.  Raw workflows are never executed
or exposed to workers by this module.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.capabilities.lease_service import CapabilityLeaseService
from engine.contracts.automation_corpus_snapshot import AutomationCorpusSnapshot
from engine.contracts.source_admission import SourceAdmission
from engine.contracts.source_artifact import SourceArtifact
from engine.contracts.worker_run import WorkerRun
from engine.core.errors import DdeError
from engine.core.hashing import sha256_hex
from engine.core.ids import uuid7
from engine.execution.service import ExecutionPlanService
from engine.object_store.durable import ScopedObjectStore, scoped_object_store_from_env
from engine.recovery.hashing import effect_response_hash
from engine.recovery.service import ExternalEffectService
from engine.source.automation import (
    ACQUISITION_POLICY_VERSION,
    MAX_COMPRESSED_BYTES,
    SOURCE_REPOSITORY,
    exact_snapshot_url,
    license_evidence,
    safe_zip_members,
    validate_http_response,
)
from engine.source.repository import SourceRepository
from engine.source.service import SourceService
from engine.truth.db import open_unit_of_work

CAPABILITY_AUTOMATION_CORPUS = "capability.automation_corpus_snapshot"
SOURCE_PROVIDER_KEY = "automation:Zie619/n8n-workflows"
SOURCE_DISPLAY_NAME = "Zie619 n8n workflow corpus"
SOURCE_SYSTEM = "github-codeload"
SOURCE_OPERATION = "GET_EXACT_SNAPSHOT"
SOURCE_COMPILER_VERSION = "dde-automation-corpus-snapshot-v2"
SOURCE_ADMISSION_POLICY_VERSION = "dde-automation-corpus-quarantine-v2"
SOURCE_SIDE_EFFECT_CLASS = "EXTERNAL_IDEMPOTENT"

FetchFn = Callable[[str], Awaitable[bytes]]


async def _default_fetch(uri: str) -> bytes:
    """Anonymous, redirect-free, bounded HTTPS fetch."""
    timeout = httpx.Timeout(45.0)
    try:
        async with httpx.AsyncClient(
            follow_redirects=False,
            trust_env=False,
            timeout=timeout,
        ) as client:
            async with client.stream("GET", uri) as response:
                validate_http_response(
                    status_code=response.status_code,
                    location=response.headers.get("location"),
                )
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_COMPRESSED_BYTES:
                        raise DdeError(
                            "BUDGET_EXCEEDED",
                            "compressed automation corpus exceeds 96 MiB",
                            retryable=False,
                        )
                return bytes(content)
    except DdeError:
        raise
    except httpx.TimeoutException as exc:
        raise TimeoutError("automation corpus acquisition timed out") from exc
    except httpx.HTTPError as exc:
        raise DdeError(
            "EXTERNAL_DEPENDENCY_FAILURE",
            "automation corpus acquisition transport failed",
            retryable=True,
            details={"error_type": type(exc).__name__},
        ) from exc


class AutomationCorpusAcquisitionService:
    """Acquire one immutable public corpus revision into quarantine."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        effects: ExternalEffectService | None = None,
        leases: CapabilityLeaseService | None = None,
        plans: ExecutionPlanService | None = None,
        sources: SourceService | None = None,
        repository: SourceRepository | None = None,
        object_store: ScopedObjectStore | None = None,
        fetch: FetchFn | None = None,
    ) -> None:
        self._engine = engine
        self._effects = effects or ExternalEffectService(engine)
        self._leases = leases or CapabilityLeaseService(engine)
        self._plans = plans or ExecutionPlanService(engine)
        self._sources = sources or SourceService(engine)
        self._repository = repository or SourceRepository()
        self._objects = object_store or scoped_object_store_from_env(
            namespace="automation-corpus"
        )
        self._fetch = fetch or _default_fetch

    async def _require_target_application(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> None:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            row = (
                await uow.connection.execute(
                    text("SELECT kind FROM projects WHERE project_id=:project_id"),
                    {"project_id": project_id},
                )
            ).first()
        if row is None or row[0] != "TARGET_APPLICATION":
            raise DdeError(
                "POLICY_DENIED",
                "automation corpus acquisition is allowed only for "
                "TARGET_APPLICATION projects",
                retryable=False,
                details={"project_id": str(project_id)},
            )

    async def acquire_snapshot(
        self,
        *,
        worker_run: WorkerRun,
        commit_sha: str,
        idempotency_key: str,
    ) -> AutomationCorpusSnapshot:
        """Fetch and persist one exact Git SHA; never accepts a branch ref."""
        tenant_id = worker_run.tenant_id
        project_id = worker_run.project_id
        uri = exact_snapshot_url(commit_sha)
        await self._require_target_application(
            tenant_id=tenant_id,
            project_id=project_id,
        )
        plan = await self._plans.get_plan(
            tenant_id=tenant_id,
            project_id=project_id,
            plan_id=worker_run.execution_plan_id,
        )
        lease = await self._leases.request(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=worker_run.mission_id,
            task_id=plan.task_id,
            execution_plan_id=plan.plan_id,
            worker_run_id=worker_run.run_id,
            environment_id=worker_run.environment_id,
            capability_id=CAPABILITY_AUTOMATION_CORPUS,
            capability_version="1",
            requested_by=(
                "engine.source.acquisition.AutomationCorpusAcquisitionService"
            ),
            idempotency_key=(f"{idempotency_key}:lease:{CAPABILITY_AUTOMATION_CORPUS}"),
        )
        if lease.status == "DENIED":
            raise DdeError(
                "POLICY_DENIED",
                "automation corpus capability lease denied",
                retryable=False,
                details={"lease_id": str(lease.lease_id)},
            )
        active_lease = await self._leases.require_active(
            tenant_id=tenant_id,
            project_id=project_id,
            worker_run_id=worker_run.run_id,
            capability_id=CAPABILITY_AUTOMATION_CORPUS,
        )

        effect = await self._effects.prepare(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=worker_run.mission_id,
            worker_run_id=worker_run.run_id,
            capability_lease_id=active_lease.lease_id,
            target_system=SOURCE_SYSTEM,
            target_resource=uri,
            operation=SOURCE_OPERATION,
            side_effect_class=SOURCE_SIDE_EFFECT_CLASS,
            idempotency_key=f"{idempotency_key}:GET:{commit_sha}",
            evidence_ref=uri,
        )
        if effect.status != "PREPARED":
            raise DdeError(
                "VERSION_CONFLICT",
                "automation corpus fetch is already journaled for this key",
                retryable=False,
                details={"effect_id": str(effect.effect_id), "status": effect.status},
            )
        await self._effects.mark_sent(
            tenant_id=tenant_id,
            project_id=project_id,
            effect_id=effect.effect_id,
        )
        try:
            archive = await self._fetch(uri)
        except TimeoutError as exc:
            await self._effects.mark_unknown(
                tenant_id=tenant_id,
                project_id=project_id,
                effect_id=effect.effect_id,
                reason=str(exc),
            )
            raise
        except Exception as exc:
            await self._effects.mark_failed(
                tenant_id=tenant_id,
                project_id=project_id,
                effect_id=effect.effect_id,
                reason=str(exc),
            )
            raise

        infos, expanded_bytes = safe_zip_members(archive)
        license_state, license_path = license_evidence(archive, infos)
        archive_hash = sha256(archive).hexdigest()
        workflow_count = sum(
            1
            for info in infos
            if not info.is_dir() and info.filename.lower().endswith(".json")
        )
        await self._effects.mark_confirmed(
            tenant_id=tenant_id,
            project_id=project_id,
            effect_id=effect.effect_id,
            external_reference=uri,
            response_hash=effect_response_hash(
                {
                    "uri": uri,
                    "archive_sha256": archive_hash,
                    "compressed_bytes": len(archive),
                }
            ),
        )

        object_ref = self._objects.put(
            tenant_id=tenant_id,
            project_id=project_id,
            content_hash=archive_hash,
            content=archive,
        )
        source = await self._sources.ensure_source(
            tenant_id=tenant_id,
            project_id=project_id,
            provider_key=SOURCE_PROVIDER_KEY,
            display_name=SOURCE_DISPLAY_NAME,
            source_domain="AUTOMATION",
            source_class="MAINTAINED_OSS",
            source_kind="PUBLIC_WORKFLOW_CORPUS",
            source_trust="S4_MAINTAINED_OSS",
            status="AVAILABLE",
            policy_revision=ACQUISITION_POLICY_VERSION,
            config={
                "repository": SOURCE_REPOSITORY,
                "acquisition_host": "codeload.github.com",
                "credentials": "FORBIDDEN",
            },
        )
        now = datetime.now(UTC)
        artifact = SourceArtifact(
            artifact_id=uuid7(),
            source_id=source.source_id,
            tenant_id=tenant_id,
            project_id=project_id,
            parent_artifact_id=None,
            artifact_kind="AUTOMATION_CORPUS_SNAPSHOT",
            provider_artifact_key=f"{SOURCE_REPOSITORY}@{commit_sha}",
            title=f"{SOURCE_REPOSITORY} {commit_sha}",
            source_uri=uri,
            revision=commit_sha,
            content_hash=archive_hash,
            content_object_ref=object_ref,
            content_object_backend=self._objects.backend_name,
            content_size_bytes=len(archive),
            media_type="application/zip",
            metadata={
                "expanded_bytes": expanded_bytes,
                "workflow_count": workflow_count,
                "license_path": license_path,
            },
            provenance={
                "repository": SOURCE_REPOSITORY,
                "commit_sha": commit_sha,
                "exact_revision": True,
                "redirects": "FORBIDDEN",
                "anonymous_https": True,
                "effect_id": str(effect.effect_id),
            },
            created_at=now,
            updated_at=now,
        )
        artifact = await self._sources.register_artifact(artifact)
        admitted = license_state == "VERIFIED"
        admission = SourceAdmission(
            admission_id=uuid7(),
            source_id=source.source_id,
            artifact_id=artifact.artifact_id,
            tenant_id=tenant_id,
            project_id=project_id,
            content_hash=archive_hash,
            compiler_version=SOURCE_COMPILER_VERSION,
            policy_version=SOURCE_ADMISSION_POLICY_VERSION,
            qualification_domain="WORKFLOW_AUTOMATION",
            qualification_profile="RAW_CORPUS_QUARANTINE",
            state="QUARANTINED" if admitted else "REJECTED",
            source_trust="S4_MAINTAINED_OSS",
            reuse_class="SOURCE_REFERENCE_ONLY" if admitted else "REJECTED",
            analysis={
                "repository": SOURCE_REPOSITORY,
                "commit_sha": commit_sha,
                "workflow_count": workflow_count,
                "expanded_bytes": expanded_bytes,
            },
            hard_failures=[] if admitted else ["LICENSE_NOT_VERIFIED"],
            validation_obligations=[
                "RAW_WORKFLOWS_MUST_REMAIN_QUARANTINED",
                "DESCRIPTORS_MUST_BE_SANITIZED_BEFORE_VEKL_QUALIFICATION",
            ],
            provenance={
                "effect_id": str(effect.effect_id),
                "object_ref": object_ref,
                "archive_sha256": archive_hash,
            },
            security_state="QUARANTINED",
            license_state=license_state,
            provenance_state="VERIFIED",
            sanitization_state="NOT_STARTED",
            injection_state="UNSCANNED",
            revoked_at=None,
            created_at=now,
            updated_at=now,
        )
        await self._sources.admit_artifact(admission)

        policy_hash = sha256_hex(
            (
                f"{ACQUISITION_POLICY_VERSION}|{SOURCE_REPOSITORY}|"
                f"{MAX_COMPRESSED_BYTES}|redirects=forbidden|credentials=forbidden"
            ).encode()
        )
        snapshot = AutomationCorpusSnapshot(
            snapshot_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            source_id=source.source_id,
            artifact_id=artifact.artifact_id,
            repository=SOURCE_REPOSITORY,
            commit_sha=commit_sha,
            archive_sha256=archive_hash,
            acquisition_policy_version=ACQUISITION_POLICY_VERSION,
            acquisition_policy_hash=policy_hash,
            acquisition_effect_id=effect.effect_id,
            acquired_at=now,
            compressed_bytes=len(archive),
            expanded_bytes=expanded_bytes,
            workflow_count=workflow_count,
            object_ref=object_ref,
            object_backend=self._objects.backend_name,
            state="QUARANTINED" if admitted else "REJECTED",
            license_state=license_state,
            license_path=license_path,
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            saved = await self._repository.insert_snapshot(uow.connection, snapshot)
            await uow.commit()
        return saved
