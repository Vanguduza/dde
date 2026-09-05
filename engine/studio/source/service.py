"""DDE-069 M8 governed Source Intelligence orchestration.

Search/inspect/fetch never mutate accepted production. External artifacts become
usable only after compiler admission; reused/adapted provenance requires an
ADMITTED exact-content record. Provider outages remain visible in search runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.design_source import DesignSource
from engine.contracts.design_source_admission import DesignSourceAdmission
from engine.contracts.design_source_artifact import DesignSourceArtifact
from engine.contracts.design_source_search_run import DesignSourceSearchRun
from engine.contracts.frontend_candidate import FrontendCandidate
from engine.contracts.frontend_candidate_score import FrontendCandidateScore
from engine.contracts.frontend_provenance_record import FrontendProvenanceRecord
from engine.contracts.frontend_source_blend_preference import (
    FrontendSourceBlendPreference,
)
from engine.contracts.frontend_template import FrontendTemplate
from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError
from engine.core.hashing import canonical_json, sha256_hex
from engine.core.ids import uuid7
from engine.object_store.durable import ScopedObjectStore, scoped_object_store_from_env
from engine.studio.candidates.lifecycle import CandidateState
from engine.studio.candidates.service import CandidateService
from engine.studio.contract.service import FrontendContractService
from engine.studio.coverage.service import compute as compute_coverage
from engine.studio.locks.service import LockService
from engine.studio.mutations.executor import MutationExecutor
from engine.studio.pxg.service import PxgService
from engine.studio.source.adapters import (
    DdeLibrarySourceAdapter,
    DesignSourceAdapter,
    DonorSourceAdapter,
    ProjectNativeSourceAdapter,
    SourceCandidate,
    SourceHealth,
    SourceQueryContext,
    TwentyFirstSourceAdapter,
    TwentyFirstTransport,
)
from engine.studio.source.blend import normalize_target_blend
from engine.studio.source.compiler import COMPILER_VERSION, evaluate_artifact
from engine.studio.source.provenance import evaluate_reusable_provenance
from engine.studio.source.repository import SourceIntelligenceRepository
from engine.studio.source.scoring import score_candidate
from engine.studio.source.twentyfirst import TwentyFirstMcpTransport
from engine.truth.db import open_unit_of_work
from engine.verification.repository import VerificationRunRepository
from engine.workspaces.service import WorkspaceService


@dataclass(frozen=True)
class SourceSearchExecution:
    run: DesignSourceSearchRun
    artifacts: tuple[DesignSourceArtifact, ...]
    sources: tuple[DesignSource, ...]


@dataclass(frozen=True)
class SourceFetchExecution:
    artifact: DesignSourceArtifact
    content: bytes | None


SOURCE_SPECS: tuple[tuple[str, str, str, str, int], ...] = (
    ("project-native", "Internal Components", "PROJECT_NATIVE", "project", 1),
    ("dde-library", "DDE Library", "DDE_LIBRARY", "catalog", 4),
    ("21st", "21st MCP", "EXTERNAL_REGISTRY", "twenty_first", 5),
    ("donors", "Donor Sources", "DONOR", "donor", 6),
)


class SourceIntelligenceService:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        repository: SourceIntelligenceRepository | None = None,
        adapters: dict[str, DesignSourceAdapter] | None = None,
        twenty_first_transport: TwentyFirstTransport | None = None,
        object_store: ScopedObjectStore | None = None,
        candidates: CandidateService | None = None,
        contracts: FrontendContractService | None = None,
        mutations: MutationExecutor | None = None,
        workspaces: WorkspaceService | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or SourceIntelligenceRepository()
        self._object_store = object_store or scoped_object_store_from_env(
            namespace="source-artifacts"
        )
        self._pxg = PxgService(engine)
        self._candidates = candidates or CandidateService(engine, pxg=self._pxg)
        self._contracts = contracts or FrontendContractService(engine)
        self._mutations = mutations or MutationExecutor(
            engine,
            pxg=self._pxg,
            locks=LockService(engine),
            candidates=self._candidates,
        )
        self._verification_runs = VerificationRunRepository()
        self._workspaces = workspaces or WorkspaceService(engine)
        twenty_first = twenty_first_transport or TwentyFirstMcpTransport(engine)
        self._adapters: dict[str, DesignSourceAdapter] = adapters or {
            "project-native": ProjectNativeSourceAdapter(engine),
            "dde-library": DdeLibrarySourceAdapter(),
            "donors": DonorSourceAdapter(engine),
            "21st": TwentyFirstSourceAdapter(twenty_first),
        }

    async def ensure_sources(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> tuple[DesignSource, ...]:
        context = SourceQueryContext(tenant_id, project_id)
        now = datetime.now(UTC)
        observed: list[tuple[tuple[str, str, str, str, int], SourceHealth | None]] = []
        for spec in SOURCE_SPECS:
            adapter = self._adapters.get(spec[0])
            health = await adapter.health(context) if adapter is not None else None
            observed.append((spec, health))
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            for (key, name, source_class, adapter_kind, priority), health in observed:
                existing = await self._repository.get_source_by_key(
                    uow.connection, project_id=project_id, provider_key=key
                )
                record = DesignSource(
                    source_id=existing.source_id if existing else uuid7(),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    provider_key=key,
                    display_name=name,
                    source_class=source_class,
                    adapter_kind=adapter_kind,
                    priority=priority,
                    status=(health.status if health else "NOT_CONFIGURED"),
                    health_detail=(
                        health.detail if health else "source catalog is not configured"
                    ),
                    capabilities=list(
                        health.capabilities if health else ("search", "inspect")
                    ),
                    config=(existing.config if existing else {}),
                    item_count=(
                        health.item_count
                        if health is not None
                        else (existing.item_count if existing else None)
                    ),
                    last_checked_at=now,
                    lock_version=existing.lock_version if existing else 1,
                    created_at=existing.created_at if existing else now,
                    updated_at=now,
                )
                await self._repository.upsert_source(uow.connection, record)
            await uow.commit()
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            return await self._repository.list_sources(
                uow.connection, project_id=project_id
            )

    async def inventory(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> tuple[DesignSource, ...]:
        """Read-only provider inventory.

        Initialization remains an explicit command/search effect.
        """
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            return await self._repository.list_sources(
                uow.connection, project_id=project_id
            )

    async def search(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID | None,
        query: str,
        provider_keys: tuple[str, ...] = (),
        requested_capabilities: tuple[str, ...] = ("search",),
    ) -> SourceSearchExecution:
        clean_query = query.strip()
        if not clean_query:
            raise DdeError("VALIDATION_FAILED", "source search query is empty")
        sources = await self.ensure_sources(tenant_id=tenant_id, project_id=project_id)
        selected = tuple(
            source
            for source in sources
            if not provider_keys or source.provider_key in provider_keys
        )
        if provider_keys:
            known = {source.provider_key for source in selected}
            unknown = tuple(key for key in provider_keys if key not in known)
            if unknown:
                raise DdeError(
                    "VALIDATION_FAILED",
                    "source search names unknown providers",
                    details={"provider_keys": list(unknown)},
                )
        now = datetime.now(UTC)
        run = DesignSourceSearchRun(
            search_run_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            query=clean_query,
            provider_keys=[source.provider_key for source in selected],
            requested_capabilities=list(requested_capabilities),
            status="RUNNING",
            result_count=0,
            degradation={},
            started_at=now,
            completed_at=None,
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            await self._repository.insert_search(uow.connection, run)
            await uow.commit()

        context = SourceQueryContext(tenant_id, project_id)
        degradation: dict[str, object] = {}
        persisted: list[DesignSourceArtifact] = []
        for source in selected:
            adapter = self._adapters.get(source.provider_key)
            if source.status not in {"AVAILABLE", "DEGRADED"} or adapter is None:
                degradation[source.provider_key] = {
                    "status": source.status,
                    "detail": source.health_detail,
                }
                continue
            try:
                candidates = await adapter.search(context, clean_query)
            except Exception as exc:
                degradation[source.provider_key] = {
                    "status": "UNAVAILABLE",
                    "detail": f"{type(exc).__name__}: {exc}",
                }
                continue
            async with open_unit_of_work(
                self._engine, tenant_id=tenant_id, project_id=project_id
            ) as uow:
                for candidate in candidates:
                    artifact = self._artifact_from_candidate(
                        source=source,
                        search_run_id=run.search_run_id,
                        candidate=candidate,
                        now=datetime.now(UTC),
                    )
                    persisted.append(
                        await self._repository.upsert_artifact(uow.connection, artifact)
                    )
                await self._repository.upsert_source(
                    uow.connection,
                    source.model_copy(
                        update={
                            "item_count": len(candidates),
                            "updated_at": datetime.now(UTC),
                        }
                    ),
                )
                await uow.commit()

        status = "COMPLETED"
        if degradation and persisted:
            status = "PARTIAL"
        elif degradation and not persisted:
            status = "BLOCKED"
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            finished = await self._repository.finish_search(
                uow.connection,
                search_run_id=run.search_run_id,
                status=status,
                result_count=len(persisted),
                degradation=degradation,
            )
            await uow.commit()
        return SourceSearchExecution(finished, tuple(persisted), selected)

    async def inspect(
        self, *, tenant_id: UUID, project_id: UUID, artifact_id: UUID
    ) -> DesignSourceArtifact:
        artifact, source = await self._artifact_and_source(
            tenant_id=tenant_id, project_id=project_id, artifact_id=artifact_id
        )
        adapter = self._adapters.get(source.provider_key)
        if adapter is None:
            raise DdeError(
                "CAPABILITY_UNAVAILABLE",
                f"source adapter {source.provider_key} is not configured",
            )
        candidate = await adapter.inspect(
            SourceQueryContext(tenant_id, project_id), artifact.provider_artifact_key
        )
        if candidate is None:
            raise DdeError("NOT_FOUND", "source artifact is no longer available")
        updated = self._artifact_from_candidate(
            source=source,
            search_run_id=artifact.search_run_id,
            candidate=candidate,
            now=datetime.now(UTC),
            artifact_id=artifact.artifact_id,
            created_at=artifact.created_at,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            saved = await self._repository.upsert_artifact(uow.connection, updated)
            await uow.commit()
        return saved

    async def fetch(
        self, *, tenant_id: UUID, project_id: UUID, artifact_id: UUID
    ) -> SourceFetchExecution:
        artifact, source = await self._artifact_and_source(
            tenant_id=tenant_id, project_id=project_id, artifact_id=artifact_id
        )
        adapter = self._adapters.get(source.provider_key)
        if adapter is None:
            raise DdeError("CAPABILITY_UNAVAILABLE", "source fetch adapter unavailable")
        fetched = await adapter.fetch(
            SourceQueryContext(tenant_id, project_id), artifact.provider_artifact_key
        )
        if fetched is None:
            raise DdeError("NOT_FOUND", "source artifact fetch returned no artifact")
        content_hash = fetched.candidate.content_hash
        if fetched.content is not None:
            observed_hash = sha256_hex(fetched.content)
            if content_hash is not None and observed_hash != content_hash:
                raise DdeError(
                    "EVIDENCE_CONFLICT",
                    "source bytes do not match provider content hash",
                    details={"expected": content_hash, "observed": observed_hash},
                )
            content_hash = observed_hash
        object_ref = artifact.content_object_ref
        object_backend = artifact.content_object_backend
        content_size = artifact.content_size_bytes
        if fetched.content is not None and content_hash is not None:
            object_ref = self._object_store.put(
                tenant_id=tenant_id,
                project_id=project_id,
                content_hash=content_hash,
                content=fetched.content,
            )
            object_backend = self._object_store.backend_name
            content_size = len(fetched.content)
        candidate = SourceCandidate(
            **{
                **fetched.candidate.__dict__,
                "content_hash": content_hash,
                "retrieval_state": "FETCHED",
            }
        )
        updated = self._artifact_from_candidate(
            source=source,
            search_run_id=artifact.search_run_id,
            candidate=candidate,
            now=datetime.now(UTC),
            artifact_id=artifact.artifact_id,
            created_at=artifact.created_at,
        ).model_copy(
            update={
                "content_object_ref": object_ref,
                "content_object_backend": object_backend,
                "content_size_bytes": content_size,
            }
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            saved = await self._repository.upsert_artifact(uow.connection, updated)
            await uow.commit()
        return SourceFetchExecution(saved, fetched.content)

    async def sandbox_adapt(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID | None,
        artifact_id: UUID,
        scope_keys: tuple[str, ...],
    ) -> tuple[FrontendCandidate, Workspace, DesignSourceArtifact, str]:
        """Materialize exact fetched source bytes into an isolated candidate worktree.

        No accepted PXG/code is mutated here. The returned derived artifact is pinned
        to the sandbox bytes and must independently pass `validate_sandbox` before it
        may become reusable candidate provenance.
        """
        if not scope_keys:
            raise DdeError(
                "VALIDATION_FAILED",
                "sandbox adaptation requires at least one candidate PXG scope key",
            )
        artifact = await self.artifact(
            tenant_id=tenant_id, project_id=project_id, artifact_id=artifact_id
        )
        if artifact is None:
            raise DdeError("NOT_FOUND", "source artifact not found")
        if artifact.content_object_ref is None or artifact.content_hash is None:
            fetched = await self.fetch(
                tenant_id=tenant_id, project_id=project_id, artifact_id=artifact_id
            )
            artifact = fetched.artifact
        if artifact.content_object_ref is None or artifact.content_hash is None:
            raise DdeError(
                "EVIDENCE_MISSING",
                "sandbox adaptation requires fetched source bytes",
            )
        content = self._object_store.read(
            tenant_id=tenant_id,
            project_id=project_id,
            key=artifact.content_object_ref,
            max_bytes=2 * 1024 * 1024,
        )
        observed = sha256_hex(content)
        if observed != artifact.content_hash:
            raise DdeError(
                "EVIDENCE_CONFLICT",
                "durable source bytes no longer match the indexed content hash",
                details={"expected": artifact.content_hash, "observed": observed},
            )
        contract = await self._contracts.get_active(
            tenant_id=tenant_id, project_id=project_id
        )
        candidate = await self._candidates.create(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            title=f"Adapt {artifact.title}",
            origin="SOURCE_IMPORT",
            scope_keys=scope_keys,
            base_contract_version=(contract.contract_version if contract else None),
            provenance={
                "source_artifact_id": str(artifact.artifact_id),
                "source_content_hash": artifact.content_hash,
                "adaptation_state": "SANDBOXED",
                **(
                    {
                        "target_blend_preference_id": str(blend.preference_id),
                        "target_blend_content_hash": blend.content_hash,
                    }
                    if (
                        blend := await self.target_blend(
                            tenant_id=tenant_id,
                            project_id=project_id,
                            scope_key=scope_keys[0],
                        )
                    )
                    is not None
                    else {}
                ),
            },
        )
        workspace = await self._workspaces.create(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            task_id=None,
            execution_environment_id=None,
            base_revision=None,
            policy={
                "purpose": "frontend-source-adaptation",
                "source_artifact_id": str(artifact.artifact_id),
                "candidate_id": str(candidate.candidate_id),
            },
        )
        candidate = await self._candidates.transition(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate.candidate_id,
            target=CandidateState.GENERATING,
            workspace_id=workspace.workspace_id,
            detail="source adaptation sandbox provisioned",
        )
        candidate = await self._candidates.transition(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate.candidate_id,
            target=CandidateState.GENERATED,
            detail="source bytes acquired",
        )
        candidate = await self._candidates.transition(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate.candidate_id,
            target=CandidateState.MATERIALIZING,
            detail="writing source bytes into isolated workspace",
        )
        suffix = ".tsx"
        if artifact.source_uri:
            observed_suffix = Path(artifact.source_uri.split("?", 1)[0]).suffix.lower()
            if observed_suffix in {
                ".tsx",
                ".ts",
                ".jsx",
                ".js",
                ".css",
                ".html",
                ".json",
            }:
                suffix = observed_suffix
        relative_path = (
            f".dde/source-adaptations/{candidate.candidate_id}/source{suffix}"
        )
        self._workspaces.write(workspace, relative_path, content)
        now = datetime.now(UTC)
        derived = artifact.model_copy(
            update={
                "artifact_id": uuid7(),
                "search_run_id": None,
                "provider_artifact_key": (
                    f"sandbox:{candidate.candidate_id}:{artifact.provider_artifact_key}"
                ),
                "title": f"{artifact.title} · sandbox adaptation",
                "source_uri": f"workspace://{workspace.workspace_id}/{relative_path}",
                "version_ref": f"sandbox:{workspace.workspace_id}:{observed}",
                "content_hash": observed,
                "content_object_ref": artifact.content_object_ref,
                "content_object_backend": artifact.content_object_backend,
                "content_size_bytes": len(content),
                "retrieval_state": "FETCHED",
                "metadata": {
                    **artifact.metadata,
                    "derived_from_artifact_id": str(artifact.artifact_id),
                    "sandbox_candidate_id": str(candidate.candidate_id),
                    "sandbox_workspace_id": str(workspace.workspace_id),
                    "sandbox_path": relative_path,
                },
                "created_at": now,
                "updated_at": now,
            }
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            derived = await self._repository.upsert_artifact(uow.connection, derived)
            await uow.commit()
        candidate = await self._candidates.transition(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate.candidate_id,
            target=CandidateState.RENDERING,
            detail="source adaptation sandbox materialized",
        )
        candidate = await self._candidates.transition(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate.candidate_id,
            target=CandidateState.READY,
            detail="sandbox source ready for adaptation/validation",
        )
        return candidate, workspace, derived, relative_path

    async def validate_sandbox(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        artifact_id: UUID,
        allow_conditional_license: bool = False,
    ) -> tuple[DesignSourceAdmission, FrontendProvenanceRecord | None]:
        """Validate the *current* isolated sandbox bytes and pin candidate provenance.

        If an editor/agent changed the file after sandbox creation, validation records a
        new exact derived artifact before admission; stale hashes are never reused.
        """
        artifact = await self.artifact(
            tenant_id=tenant_id, project_id=project_id, artifact_id=artifact_id
        )
        if artifact is None:
            raise DdeError("NOT_FOUND", "sandbox source artifact not found")
        metadata = artifact.metadata
        candidate_raw = metadata.get("sandbox_candidate_id")
        workspace_raw = metadata.get("sandbox_workspace_id")
        relative_path = metadata.get("sandbox_path")
        if not all(
            isinstance(item, str) and item
            for item in (candidate_raw, workspace_raw, relative_path)
        ):
            raise DdeError(
                "VALIDATION_FAILED",
                "source artifact is not a DDE sandbox adaptation",
            )
        candidate_id = UUID(str(candidate_raw))
        workspace = await self._workspaces.get_workspace(
            tenant_id=tenant_id,
            project_id=project_id,
            workspace_id=UUID(str(workspace_raw)),
        )
        content = self._workspaces.read(workspace, str(relative_path))
        observed = sha256_hex(content)
        current = artifact
        if artifact.content_hash != observed:
            now = datetime.now(UTC)
            object_ref = self._object_store.put(
                tenant_id=tenant_id,
                project_id=project_id,
                content_hash=observed,
                content=content,
            )
            current = artifact.model_copy(
                update={
                    "artifact_id": uuid7(),
                    "provider_artifact_key": (
                        f"{artifact.provider_artifact_key}:rev:{observed[:12]}"
                    ),
                    "content_hash": observed,
                    "content_object_ref": object_ref,
                    "content_object_backend": self._object_store.backend_name,
                    "content_size_bytes": len(content),
                    "version_ref": f"sandbox:{workspace.workspace_id}:{observed}",
                    "retrieval_state": "FETCHED",
                    "metadata": {
                        **metadata,
                        "supersedes_artifact_id": str(artifact.artifact_id),
                    },
                    "created_at": now,
                    "updated_at": now,
                }
            )
            async with open_unit_of_work(
                self._engine, tenant_id=tenant_id, project_id=project_id
            ) as uow:
                current = await self._repository.upsert_artifact(
                    uow.connection, current
                )
                await uow.commit()
        validation = {
            "state": "CURRENT_BYTES_VALIDATED",
            "candidate_id": str(candidate_id),
            "workspace_id": str(workspace.workspace_id),
            "content_hash": observed,
            "validation_kind": "DDE_SOURCE_COMPILER_CURRENT_BYTES",
        }
        current = current.model_copy(
            update={
                "metadata": {**current.metadata, "sandbox_validation": validation},
                "updated_at": datetime.now(UTC),
            }
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            current = await self._repository.upsert_artifact(uow.connection, current)
            await uow.commit()
        admission = await self.admit(
            tenant_id=tenant_id,
            project_id=project_id,
            artifact_id=current.artifact_id,
            project_frameworks=(current.framework,) if current.framework else (),
            allow_conditional_license=allow_conditional_license,
        )
        provenance = None
        if admission.state == "ADMITTED":
            provenance = await self.record_provenance(
                tenant_id=tenant_id,
                project_id=project_id,
                subject_kind="CANDIDATE",
                subject_ref=str(candidate_id),
                artifact_id=current.artifact_id,
                usage_kind="ADAPTED",
            )
        return admission, provenance

    async def admit(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        artifact_id: UUID,
        project_frameworks: tuple[str, ...] = (),
        allow_conditional_license: bool = False,
    ) -> DesignSourceAdmission:
        artifact, _ = await self._artifact_and_source(
            tenant_id=tenant_id, project_id=project_id, artifact_id=artifact_id
        )
        if not artifact.content_hash:
            raise DdeError(
                "EVIDENCE_MISSING",
                "source admission requires exact fetched content hash",
            )
        if (
            artifact.artifact_kind in {"COMPONENT", "TEMPLATE", "THEME", "FOUNDATION"}
            and not artifact.content_object_ref
        ):
            raise DdeError(
                "EVIDENCE_MISSING",
                "reusable source admission requires durably stored fetched bytes",
            )
        decision = evaluate_artifact(
            artifact,
            project_frameworks=project_frameworks,
            allow_conditional_license=allow_conditional_license,
        )
        now = datetime.now(UTC)
        record = DesignSourceAdmission(
            admission_id=uuid7(),
            artifact_id=artifact.artifact_id,
            tenant_id=tenant_id,
            project_id=project_id,
            content_hash=artifact.content_hash,
            compiler_version=COMPILER_VERSION,
            framework_state=decision.framework_state,
            license_state=decision.license_state,
            dependency_state=decision.dependency_state,
            security_state=decision.security_state,
            accessibility_state=decision.accessibility_state,
            design_system_state=decision.design_system_state,
            token_mapping_report=decision.token_mapping_report,
            unsupported_behaviors=list(decision.unsupported_behaviors),
            hard_failures=list(decision.hard_failures),
            validation_obligations=list(decision.validation_obligations),
            state=decision.state,
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            saved = await self._repository.insert_admission(uow.connection, record)
            await self._repository.upsert_artifact(
                uow.connection,
                artifact.model_copy(
                    update={
                        "retrieval_state": {
                            "ADMITTED": "ADMITTED",
                            "REJECTED": "REJECTED",
                            "BLOCKED": "BLOCKED",
                        }[saved.state],
                        "updated_at": now,
                    }
                ),
            )
            await uow.commit()
        return saved

    async def record_provenance(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        subject_kind: str,
        subject_ref: str,
        artifact_id: UUID,
        usage_kind: str,
        attribution_weight: float | None = None,
        decision_ref: str | None = None,
    ) -> FrontendProvenanceRecord:
        artifact, source = await self._artifact_and_source(
            tenant_id=tenant_id, project_id=project_id, artifact_id=artifact_id
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            admission = await self._repository.latest_admission(
                uow.connection, artifact_id=artifact_id
            )
        decision = evaluate_reusable_provenance(
            artifact=artifact,
            source=source,
            admission=admission,
            usage_kind=usage_kind,
            subject_kind=subject_kind,
            subject_ref=subject_ref,
            recorded_admission_id=(admission.admission_id if admission else None),
        )
        if not decision.allowed:
            raise DdeError(
                "POLICY_DENIED",
                decision.detail,
                details={
                    "artifact_id": str(artifact.artifact_id),
                    "provider_key": source.provider_key,
                    "usage_kind": usage_kind,
                },
            )
        now = datetime.now(UTC)
        record = FrontendProvenanceRecord(
            provenance_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            subject_kind=subject_kind,
            subject_ref=subject_ref,
            source_id=artifact.source_id,
            artifact_id=artifact.artifact_id,
            admission_id=admission.admission_id if admission else None,
            usage_kind=usage_kind,
            attribution_weight=attribution_weight,
            source_revision=artifact.version_ref or artifact.content_hash,
            license_state=artifact.license_state,
            security_state=artifact.security_state,
            decision_ref=decision_ref,
            metadata={
                "provider_artifact_key": artifact.provider_artifact_key,
                "source_class": source.source_class,
                "sandbox_validation": artifact.metadata.get("sandbox_validation"),
            },
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            await self._repository.insert_provenance(uow.connection, record)
            await uow.commit()
        return record

    async def recommend_templates(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> tuple[FrontendTemplate, ...]:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            artifacts = await self._repository.list_artifacts(
                uow.connection, project_id=project_id
            )
        created: list[FrontendTemplate] = []
        for artifact in artifacts:
            if artifact.artifact_kind not in {"TEMPLATE", "FOUNDATION"}:
                continue
            async with open_unit_of_work(
                self._engine, tenant_id=tenant_id, project_id=project_id
            ) as uow:
                admission = await self._repository.latest_admission(
                    uow.connection, artifact_id=artifact.artifact_id
                )
            hard = tuple(admission.hard_failures) if admission else ("NOT_ADMITTED",)
            score_summary = {
                "license": artifact.license_state,
                "security": artifact.security_state,
                "accessibility": artifact.accessibility_state,
                "compatibility": artifact.compatibility_state,
            }
            now = datetime.now(UTC)
            template = FrontendTemplate(
                template_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                source_artifact_id=artifact.artifact_id,
                title=artifact.title,
                source_refs=[str(artifact.artifact_id)],
                supported_archetypes=list(artifact.supported_archetypes),
                expected_screen_coverage=None,
                score_summary=score_summary,
                hard_failures=list(hard),
                status="REJECTED" if hard else "RECOMMENDED",
                content_hash=artifact.content_hash,
                created_at=now,
                updated_at=now,
            )
            async with open_unit_of_work(
                self._engine, tenant_id=tenant_id, project_id=project_id
            ) as uow:
                await self._repository.insert_template(uow.connection, template)
                await uow.commit()
            created.append(template)
        return tuple(created)

    async def compute_candidate_score(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
    ) -> FrontendCandidateScore:
        """Compute a score only from DDE-owned candidate evidence.

        A missing candidate-specific evaluator leaves that dimension absent, which
        deliberately yields UNSCORED rather than a client-supplied or accepted-state
        approximation.
        """
        candidate = await self._candidates.get(
            tenant_id=tenant_id, project_id=project_id, candidate_id=candidate_id
        )
        graph = await self._mutations.candidate_graph(
            tenant_id=tenant_id, project_id=project_id, candidate_id=candidate_id
        )
        contract = await self._contracts.get_active(
            tenant_id=tenant_id, project_id=project_id
        )
        verification = None
        if candidate.verification_run_id is not None:
            async with open_unit_of_work(
                self._engine, tenant_id=tenant_id, project_id=project_id
            ) as uow:
                verification = await self._verification_runs.get_run(
                    uow.connection, candidate.verification_run_id
                )
            if verification is not None and (
                verification.subject_kind != "FRONTEND_CANDIDATE"
                or verification.subject_id != candidate_id
                or verification.project_id != project_id
            ):
                verification = None

        dimensions: dict[str, dict[str, object]] = {}
        hard: list[str] = []
        if verification is not None and verification.status == "PASSED":
            dimensions["product_fit"] = {
                "score": round(float(verification.confidence) * 100.0, 2),
                "evidence_refs": [f"verification:{verification.verification_run_id}"],
            }

        if contract is not None:
            passing: dict[str, set[str]] = {}
            if verification is not None and verification.status == "PASSED":
                for check in verification.check_results:
                    if check.status != "PASSED" or ":" not in check.check_ref:
                        continue
                    key, _sep, _tail = check.check_ref.rpartition(":")
                    passing.setdefault(key, set()).add(check.kind)
            computed = compute_coverage(
                contract,
                graph,
                passing_verifications={
                    key: frozenset(value) for key, value in passing.items()
                },
            )
            if computed.weighted_percent is not None:
                dimensions["feature_coverage"] = {
                    "score": computed.weighted_percent,
                    "evidence_refs": [
                        f"candidate-coverage:{candidate_id}:{contract.contract_version}:pxg-{graph.revision}"
                    ],
                }
            by_name = {item.dimension.lower(): item for item in computed.dimensions}
            for score_name, aliases in (
                ("responsive_fit", ("responsive", "responsiveness")),
                ("accessibility_fit", ("accessibility", "a11y")),
                ("architecture_fit", ("architecture", "navigation", "journey")),
            ):
                matched = [by_name[name] for name in aliases if name in by_name]
                values = [item.percent for item in matched if item.percent is not None]
                if values:
                    dimensions[score_name] = {
                        "score": round(sum(values) / len(values), 2),
                        "evidence_refs": [
                            f"candidate-coverage:{candidate_id}:{item.dimension}:pxg-{graph.revision}"
                            for item in matched
                            if item.percent is not None
                        ],
                    }

        provenance = await self.provenance_for_subject(
            tenant_id=tenant_id,
            project_id=project_id,
            subject_kind="CANDIDATE",
            subject_ref=str(candidate_id),
        )
        reusable = [
            row for row in provenance if row.usage_kind in {"REUSED", "ADAPTED"}
        ]
        admission_rows: list[DesignSourceAdmission] = []
        native_refs: list[str] = []
        for row in reusable:
            if row.artifact_id is None:
                hard.append("PROVENANCE_ARTIFACT_MISSING")
                continue
            try:
                artifact, source = await self._artifact_and_source(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    artifact_id=row.artifact_id,
                )
            except DdeError:
                hard.append("PROVENANCE_SOURCE_MISSING")
                continue
            admission = await self.admission_for_artifact(
                tenant_id=tenant_id,
                project_id=project_id,
                artifact_id=row.artifact_id,
            )
            decision = evaluate_reusable_provenance(
                artifact=artifact,
                source=source,
                admission=admission,
                usage_kind=row.usage_kind,
                subject_kind="CANDIDATE",
                subject_ref=str(candidate_id),
                recorded_admission_id=row.admission_id,
            )
            if not decision.allowed:
                hard.append("PROVENANCE_ADMISSION_STALE")
                continue
            if source.source_class == "PROJECT_NATIVE":
                native_refs.append(f"project-native:{artifact.provider_artifact_key}")
                continue
            if admission is not None:
                admission_rows.append(admission)

        if native_refs or admission_rows:
            source_refs = [
                *native_refs,
                *(f"admission:{row.admission_id}" for row in admission_rows),
            ]
            dimensions["design_system_fit"] = {
                "score": 100.0
                if all(row.design_system_state == "PASS" for row in admission_rows)
                else (100.0 if native_refs and not admission_rows else 0.0),
                "evidence_refs": source_refs,
            }
            dimensions["dependency_posture"] = {
                "score": 100.0
                if all(row.dependency_state == "PASS" for row in admission_rows)
                else (100.0 if native_refs and not admission_rows else 0.0),
                "evidence_refs": source_refs,
            }
            dimensions["license_confidence"] = {
                "score": 100.0
                if all(row.license_state == "PASS" for row in admission_rows)
                else (100.0 if native_refs and not admission_rows else 70.0),
                "evidence_refs": source_refs,
            }
            dimensions["provenance_confidence"] = {
                "score": 100.0,
                "evidence_refs": [
                    f"provenance:{row.provenance_id}" for row in reusable
                ],
            }
            if admission_rows:
                dimensions["security_posture"] = {
                    "score": 100.0
                    if all(row.security_state == "PASS" for row in admission_rows)
                    else 0.0,
                    "evidence_refs": [
                        f"admission:{row.admission_id}" for row in admission_rows
                    ],
                }
        elif candidate.origin in {"SOURCE_IMPORT", "TEMPLATE_BLEND"}:
            hard.append("SOURCE_DERIVED_CANDIDATE_WITHOUT_REUSABLE_PROVENANCE")

        return await self.record_candidate_score(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
            verification_run_id=(
                verification.verification_run_id if verification is not None else None
            ),
            dimensions=dimensions,
            hard_failures=tuple(dict.fromkeys(hard)),
        )

    async def record_candidate_score(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
        verification_run_id: UUID | None,
        dimensions: dict[str, dict[str, object]],
        hard_failures: tuple[str, ...] = (),
    ) -> FrontendCandidateScore:
        decision = score_candidate(dimensions, hard_failures=hard_failures)
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            sequence = await self._repository.next_score_sequence(
                uow.connection, candidate_id=candidate_id
            )
            record = FrontendCandidateScore(
                score_id=uuid7(),
                candidate_id=candidate_id,
                tenant_id=tenant_id,
                project_id=project_id,
                sequence=sequence,
                verification_run_id=verification_run_id,
                score_state=decision.score_state,
                overall_score=decision.overall_score,
                classification=decision.classification,
                dimensions=decision.dimensions,
                hard_failures=list(decision.hard_failures),
                evidence_refs=list(decision.evidence_refs),
                computed_at=now,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_score(uow.connection, record)
            await uow.commit()
        return record

    async def latest_candidate_score(
        self, *, tenant_id: UUID, project_id: UUID, candidate_id: UUID
    ) -> FrontendCandidateScore | None:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            return await self._repository.latest_score(
                uow.connection, candidate_id=candidate_id
            )

    async def target_blend(
        self, *, tenant_id: UUID, project_id: UUID, scope_key: str
    ) -> FrontendSourceBlendPreference | None:
        """Return the active exact-scope preference, falling back to project `*`."""
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            exact = await self._repository.active_source_blend(
                uow.connection, project_id=project_id, scope_key=scope_key
            )
            if exact is not None or scope_key == "*":
                return exact
            return await self._repository.active_source_blend(
                uow.connection, project_id=project_id, scope_key="*"
            )

    async def set_target_blend(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID | None,
        scope_key: str,
        weights: dict[str, float],
        created_by: UUID | None,
    ) -> FrontendSourceBlendPreference:
        scope = scope_key.strip() or "*"
        normalized = normalize_target_blend(
            weights, known_provider_keys=frozenset(item[0] for item in SOURCE_SPECS)
        )
        now = datetime.now(UTC)
        content_hash = sha256_hex(
            canonical_json({"scope_key": scope, "weights": normalized})
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            prior = await self._repository.active_source_blend(
                uow.connection, project_id=project_id, scope_key=scope
            )
            if prior is not None and prior.content_hash == content_hash:
                return prior
            record = FrontendSourceBlendPreference(
                preference_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                scope_key=scope,
                weights=normalized,
                status="ACTIVE",
                content_hash=content_hash,
                created_by=created_by,
                supersedes_id=prior.preference_id if prior else None,
                lock_version=1,
                created_at=now,
                updated_at=now,
            )
            await self._repository.replace_source_blend(uow.connection, record)
            await uow.commit()
        return record

    async def promotion_readiness(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
        candidate_origin: str,
    ) -> tuple[bool, str]:
        records = await self.provenance_for_subject(
            tenant_id=tenant_id,
            project_id=project_id,
            subject_kind="CANDIDATE",
            subject_ref=str(candidate_id),
        )
        provenance_required = candidate_origin in {
            "SOURCE_IMPORT",
            "TEMPLATE_BLEND",
            "DESIGN_ARTIFACT",
        }
        if provenance_required and not records:
            return False, "source-derived candidate has no candidate provenance"
        if candidate_origin in {"SOURCE_IMPORT", "TEMPLATE_BLEND"} and not any(
            row.usage_kind in {"REUSED", "ADAPTED"} for row in records
        ):
            return (
                False,
                "source/template candidate has no reusable admitted provenance",
            )
        accepted_graph = None
        for record in records:
            if record.usage_kind not in {"REUSED", "ADAPTED"}:
                continue
            if record.artifact_id is None:
                return False, "reused/adapted provenance has no source artifact"
            try:
                artifact, source = await self._artifact_and_source(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    artifact_id=record.artifact_id,
                )
            except DdeError:
                return False, "provenance references missing source evidence"
            admission = await self.admission_for_artifact(
                tenant_id=tenant_id,
                project_id=project_id,
                artifact_id=record.artifact_id,
            )
            decision = evaluate_reusable_provenance(
                artifact=artifact,
                source=source,
                admission=admission,
                usage_kind=record.usage_kind,
                subject_kind="CANDIDATE",
                subject_ref=str(candidate_id),
                recorded_admission_id=record.admission_id,
            )
            if not decision.allowed:
                return False, decision.detail
            if source.source_class == "PROJECT_NATIVE":
                if accepted_graph is None:
                    accepted_graph = await self._pxg.load(
                        tenant_id=tenant_id, project_id=project_id
                    )
                if accepted_graph.node_by_key(artifact.provider_artifact_key) is None:
                    return False, "project-native provenance points at a stale PXG node"
        return True, (
            f"{len(records)} provenance record(s); reusable source evidence admitted"
        )

    async def carry_candidate_provenance_to_pxg(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
        scope_keys: tuple[str, ...],
        accepted_revision: str | None,
    ) -> tuple[FrontendProvenanceRecord, ...]:
        """Project already-gated candidate attribution onto accepted PXG nodes.

        This is a derived projection performed only after promotion. Multi-scope
        candidates deliberately drop numeric attribution weight because a candidate-
        level fraction cannot be truthfully copied onto every node.
        """
        rows = await self.provenance_for_subject(
            tenant_id=tenant_id,
            project_id=project_id,
            subject_kind="CANDIDATE",
            subject_ref=str(candidate_id),
        )
        if not rows or not scope_keys:
            return ()
        projected: list[FrontendProvenanceRecord] = []
        for target in scope_keys:
            for row in rows:
                if row.artifact_id is None:
                    continue
                projected_row = await self.record_provenance(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    subject_kind="PXG_NODE",
                    subject_ref=target,
                    artifact_id=row.artifact_id,
                    usage_kind=row.usage_kind,
                    attribution_weight=(
                        row.attribution_weight if len(scope_keys) == 1 else None
                    ),
                    decision_ref=row.decision_ref,
                )
                metadata = {
                    **projected_row.metadata,
                    "promoted_from_candidate_id": str(candidate_id),
                    "candidate_provenance_id": str(row.provenance_id),
                    "candidate_attribution_weight": row.attribution_weight,
                    "accepted_revision": accepted_revision,
                }
                async with open_unit_of_work(
                    self._engine, tenant_id=tenant_id, project_id=project_id
                ) as uow:
                    await self._repository.update_provenance_metadata(
                        uow.connection,
                        provenance_id=projected_row.provenance_id,
                        metadata=metadata,
                    )
                    await uow.commit()
                projected.append(
                    projected_row.model_copy(update={"metadata": metadata})
                )
        return tuple(projected)

    async def provenance_for_subject(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        subject_kind: str,
        subject_ref: str,
    ) -> tuple[FrontendProvenanceRecord, ...]:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            return await self._repository.provenance_for_subject(
                uow.connection,
                project_id=project_id,
                subject_kind=subject_kind,
                subject_ref=subject_ref,
            )

    async def artifact(
        self, *, tenant_id: UUID, project_id: UUID, artifact_id: UUID
    ) -> DesignSourceArtifact | None:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            artifact = await self._repository.get_artifact(
                uow.connection, artifact_id=artifact_id
            )
        if artifact is None or artifact.project_id != project_id:
            return None
        return artifact

    async def admission_for_artifact(
        self, *, tenant_id: UUID, project_id: UUID, artifact_id: UUID
    ) -> DesignSourceAdmission | None:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            return await self._repository.latest_admission(
                uow.connection, artifact_id=artifact_id
            )

    async def artifacts(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> tuple[DesignSourceArtifact, ...]:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            return await self._repository.list_artifacts(
                uow.connection, project_id=project_id
            )

    async def templates(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> tuple[FrontendTemplate, ...]:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            return await self._repository.list_templates(
                uow.connection, project_id=project_id
            )

    async def _artifact_and_source(
        self, *, tenant_id: UUID, project_id: UUID, artifact_id: UUID
    ) -> tuple[DesignSourceArtifact, DesignSource]:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            artifact = await self._repository.get_artifact(
                uow.connection, artifact_id=artifact_id
            )
            if artifact is None or artifact.project_id != project_id:
                raise DdeError("NOT_FOUND", "source artifact not found")
            sources = await self._repository.list_sources(
                uow.connection, project_id=project_id
            )
        source = next(
            (row for row in sources if row.source_id == artifact.source_id), None
        )
        if source is None:
            raise DdeError("CONTEXT_INCOMPLETE", "source registry row is missing")
        return artifact, source

    @staticmethod
    def _artifact_from_candidate(
        *,
        source: DesignSource,
        search_run_id: UUID | None,
        candidate: SourceCandidate,
        now: datetime,
        artifact_id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> DesignSourceArtifact:
        return DesignSourceArtifact(
            artifact_id=artifact_id or uuid7(),
            source_id=source.source_id,
            search_run_id=search_run_id,
            tenant_id=source.tenant_id,
            project_id=source.project_id,
            provider_artifact_key=candidate.provider_artifact_key,
            artifact_kind=candidate.artifact_kind,
            title=candidate.title,
            source_uri=candidate.source_uri,
            version_ref=candidate.version_ref,
            content_hash=candidate.content_hash,
            content_object_ref=None,
            content_object_backend=None,
            content_size_bytes=None,
            framework=candidate.framework,
            supported_archetypes=list(candidate.supported_archetypes),
            dependency_manifest=list(candidate.dependency_manifest),
            license_state=candidate.license_state,
            license_ids=list(candidate.license_ids),
            security_state=candidate.security_state,
            accessibility_state=candidate.accessibility_state,
            compatibility_state=candidate.compatibility_state,
            retrieval_state=candidate.retrieval_state,
            metadata=dict(candidate.metadata),
            created_at=created_at or now,
            updated_at=now,
        )
