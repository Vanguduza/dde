"""Donor Lab ingest service — production mutation sites for DDE-046/047.

Chapter 13.8 / owner pin-by-URL:
- `submit_uri` is the durable ingest call site for human-supplied
  `source_uri` (Studio Donors field and Chat/MCP both target this; Gateway
  command `frontend.donors.submit_uri` wires in DDE-067).
- Offline/fixture vertical slice: content bytes or a local file path.
  Remote http(s) fetch without attached content is refused (discovery
  egress is DDE-066 / EDR-0015, not silent fetch here).
- Licence/reuse classifier runs BEFORE persistence; UNKNOWN/conflicting
  defaults to SOURCE_REFERENCE_ONLY (or REJECTED per policy).
- Feature DNA stub + donor_taints (feature_dna subject) written in the
  same unit of work so "which donor influenced this" is answerable.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.donor_artifact import DonorArtifact
from engine.contracts.feature_dna import FeatureDNA
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.hashing import sha256_hex
from engine.core.ids import uuid7
from engine.donor.classify import classify_donor
from engine.donor.extract import build_feature_dna_stub
from engine.donor.injection import screen_donor_text
from engine.donor.repository import DonorRepository
from engine.donor.taint import DonorTaintService
from engine.events.idempotency import CommandLedger
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

AUTHORITY_RANK_EXTERNAL = 9
COMMAND_TYPE = "frontend.donors.submit_uri"

T = TypeVar("T")

_MEDIA_KINDS = frozenset(
    {"registry_json", "readme", "licence_text", "source_tree", "other"}
)


@dataclass(frozen=True)
class IngestResult:
    artifact: DonorArtifact
    feature_dna: FeatureDNA
    replayed: bool


class DonorLabService:
    """Owns donor_artifacts + feature_dna + initial taint inserts (Ch.3.8)."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: DonorRepository | None = None,
        commands: CommandLedger | None = None,
        taints: DonorTaintService | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or DonorRepository()
        self._commands = commands or CommandLedger(engine)
        self._taints = taints or DonorTaintService(engine, repository=self._repository)
        self._clock = clock or SystemClock()

    async def _run(
        self,
        uow: PostgresUnitOfWork | None,
        tenant_id: UUID,
        project_id: UUID,
        body: Callable[[PostgresUnitOfWork], Awaitable[T]],
    ) -> T:
        if uow is not None:
            return await body(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as owned:
            outcome = await body(owned)
            await owned.commit()
            return outcome

    async def get_artifact(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        donor_artifact_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> DonorArtifact | None:
        async def _op(active: PostgresUnitOfWork) -> DonorArtifact | None:
            return await self._repository.get_artifact(
                active.connection, donor_artifact_id
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def get_feature_dna(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        feature_dna_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> FeatureDNA | None:
        async def _op(active: PostgresUnitOfWork) -> FeatureDNA | None:
            return await self._repository.get_feature_dna(
                active.connection, feature_dna_id
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def submit_uri(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        source_uri: str,
        idempotency_key: str,
        content: bytes | None = None,
        content_path: str | Path | None = None,
        media_kind: str = "other",
        source_class: str | None = None,
        signed_reuse_decision_id: UUID | None = None,
        mission_id: UUID | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> IngestResult:
        """Pin a donor by address — classify then persist (DDE-046/047)."""
        uri = source_uri.strip()
        if not uri:
            raise DdeError(
                "POLICY_DENIED",
                "source_uri must be non-empty",
                details={"field": "source_uri"},
            )
        if media_kind not in _MEDIA_KINDS:
            raise DdeError(
                "POLICY_DENIED",
                f"Unknown media_kind {media_kind!r}",
                details={"media_kind": media_kind},
            )

        payload = self._load_content(
            source_uri=uri, content=content, content_path=content_path
        )
        content_hash = sha256_hex(payload)
        text = payload.decode("utf-8", errors="replace")
        classification = classify_donor(
            text,
            requested_source_class=source_class,
            signed_reuse_decision_id=signed_reuse_decision_id,
            source_uri=uri,
        )
        resolved_class = classification.source_class
        findings = screen_donor_text(text)
        request_hash = sha256_hex(
            f"{COMMAND_TYPE}|{uri}|{content_hash}|{resolved_class}|{media_kind}".encode()
        )

        async def _op(active: PostgresUnitOfWork) -> IngestResult:
            record, is_new = await self._commands.begin(
                tenant_id=tenant_id,
                project_id=project_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                uow=active,
            )
            if not is_new:
                return await self._replay(active, record)

            existing = await self._repository.find_by_content_hash(
                active.connection, project_id=project_id, content_hash=content_hash
            )
            if existing is not None and existing.feature_dna_id is not None:
                dna = await self._repository.get_feature_dna(
                    active.connection, existing.feature_dna_id
                )
                if dna is None:
                    raise DdeError(
                        "POLICY_DENIED",
                        "Donor artifact references missing Feature DNA",
                        details={
                            "donor_artifact_id": str(existing.donor_artifact_id),
                            "feature_dna_id": str(existing.feature_dna_id),
                        },
                    )
                result = IngestResult(artifact=existing, feature_dna=dna, replayed=True)
                await self._commands.complete(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    command_id=record.command_id,
                    result=self._result_payload(result),
                    uow=active,
                )
                return result

            now = self._clock.now()
            artifact_id = uuid7()
            dna_id = uuid7()
            # Re-classify with concrete artifact id so taint tags are final.
            classification_final = classify_donor(
                text,
                requested_source_class=source_class,
                signed_reuse_decision_id=signed_reuse_decision_id,
                donor_artifact_id=artifact_id,
                source_uri=uri,
            )
            tags = list(classification_final.taint_tags)
            title, body, dna_hash = build_feature_dna_stub(
                source_uri=uri,
                content_hash=content_hash,
                media_kind=media_kind,
                source_class=classification_final.source_class,
                injection_findings=findings,
                licence_class=classification_final.licence_class,
                classification_evidence=[classification_final.rationale],
            )
            prior_dna = await self._repository.find_feature_dna_by_hash(
                active.connection, project_id=project_id, dna_hash=dna_hash
            )
            if prior_dna is not None:
                dna_id = prior_dna.feature_dna_id

            artifact = DonorArtifact(
                donor_artifact_id=artifact_id,
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                source_uri=uri,
                content_hash=content_hash,
                source_class=classification_final.source_class,
                authority_rank=AUTHORITY_RANK_EXTERNAL,
                media_kind=media_kind,
                status="INGESTED",
                provenance={
                    "entry": "manual_pin",
                    "command_type": COMMAND_TYPE,
                    "idempotency_key": idempotency_key,
                    "signed_reuse_decision_id": (
                        str(signed_reuse_decision_id)
                        if signed_reuse_decision_id is not None
                        else None
                    ),
                    "licence_class": classification_final.licence_class,
                    "classification_rationale": classification_final.rationale,
                    "content_bytes": len(payload),
                },
                feature_dna_id=None,
                injection_findings=findings,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_artifact(active.connection, artifact)

            if prior_dna is None:
                dna = FeatureDNA(
                    feature_dna_id=dna_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    donor_artifact_id=artifact_id,
                    title=title,
                    body=body,
                    donor_sources=[uri],
                    dna_hash=dna_hash,
                    taint_tags=tags,
                    status="STUB",
                    created_at=now,
                    updated_at=now,
                )
                await self._repository.insert_feature_dna(active.connection, dna)
            else:
                dna = prior_dna

            await self._repository.update_artifact_feature_dna(
                active.connection,
                artifact_id,
                feature_dna_id=dna.feature_dna_id,
                status="EXTRACTED",
                updated_at=now,
            )
            artifact = artifact.model_copy(
                update={
                    "feature_dna_id": dna.feature_dna_id,
                    "status": "EXTRACTED",
                    "updated_at": now,
                }
            )
            await self._taints.link(
                tenant_id=tenant_id,
                project_id=project_id,
                donor_artifact_id=artifact_id,
                subject_kind="feature_dna",
                subject_id=dna.feature_dna_id,
                source_class=classification_final.source_class,
                licence_class=classification_final.licence_class,
                source_uri=uri,
                signed_reuse_decision_id=signed_reuse_decision_id,
                taint_tags=tags,
                uow=active,
            )
            result = IngestResult(artifact=artifact, feature_dna=dna, replayed=False)
            await self._commands.complete(
                tenant_id=tenant_id,
                project_id=project_id,
                command_id=record.command_id,
                result=self._result_payload(result),
                uow=active,
            )
            return result

        return await self._run(uow, tenant_id, project_id, _op)

    def _load_content(
        self,
        *,
        source_uri: str,
        content: bytes | None,
        content_path: str | Path | None,
    ) -> bytes:
        if content is not None and content_path is not None:
            raise DdeError(
                "POLICY_DENIED",
                "Pass either content bytes or content_path, not both",
            )
        if content is not None:
            return content
        if content_path is not None:
            path = Path(content_path)
            if not path.is_file():
                raise DdeError(
                    "POLICY_DENIED",
                    "Donor content_path is not a readable file",
                    details={"content_path": str(path)},
                )
            return path.read_bytes()
        lowered = source_uri.lower()
        if lowered.startswith("http://") or lowered.startswith("https://"):
            raise DdeError(
                "POLICY_DENIED",
                "Remote donor fetch is not admitted on the DDE-046 ingest "
                "path; supply content bytes/fixture path, or use DDE-066 "
                "discovery after EDR-0015 egress",
                details={
                    "source_uri": source_uri,
                    "deferred": "DDE-066",
                },
            )
        if lowered.startswith("file:"):
            raw = source_uri[5:]
            if raw.startswith("///"):
                path = Path(raw[3:])
            elif raw.startswith("//"):
                path = Path(raw[2:])
            else:
                path = Path(raw)
            if not path.is_file():
                raise DdeError(
                    "POLICY_DENIED",
                    "file: source_uri does not resolve to a readable file",
                    details={"source_uri": source_uri, "path": str(path)},
                )
            return path.read_bytes()
        path = Path(source_uri)
        if path.is_file():
            return path.read_bytes()
        raise DdeError(
            "POLICY_DENIED",
            "Donor ingest requires content bytes, content_path, or a local "
            "file: / filesystem source_uri (remote http(s) refused here)",
            details={"source_uri": source_uri},
        )

    def _result_payload(self, result: IngestResult) -> dict[str, object]:
        return {
            "donor_artifact_id": str(result.artifact.donor_artifact_id),
            "feature_dna_id": str(result.feature_dna.feature_dna_id),
            "content_hash": result.artifact.content_hash,
            "source_class": result.artifact.source_class,
            "replayed": result.replayed,
        }

    async def _replay(self, active: PostgresUnitOfWork, record: object) -> IngestResult:
        status = getattr(record, "status", None)
        stored = getattr(record, "result", None)
        if status == "completed" and isinstance(stored, dict):
            artifact_id = stored.get("donor_artifact_id")
            dna_id = stored.get("feature_dna_id")
            if isinstance(artifact_id, str) and isinstance(dna_id, str):
                artifact = await self._repository.get_artifact(
                    active.connection, UUID(artifact_id)
                )
                dna = await self._repository.get_feature_dna(
                    active.connection, UUID(dna_id)
                )
                if artifact is None or dna is None:
                    raise DdeError(
                        "POLICY_DENIED",
                        "Completed donor ingest ledger result missing rows",
                        details=dict(stored),
                    )
                return IngestResult(artifact=artifact, feature_dna=dna, replayed=True)
        if status == "in_progress":
            raise DdeError(
                "VERSION_CONFLICT",
                "Donor ingest command still in progress",
                details={"idempotency_key": getattr(record, "idempotency_key", None)},
                retryable=True,
            )
        raise DdeError(
            "POLICY_DENIED",
            "Donor ingest idempotency key is not in a replayable completed state",
            details={
                "status": status,
                "idempotency_key": getattr(record, "idempotency_key", None),
            },
        )
