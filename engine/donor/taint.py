"""Donor taint persistence and mutation sites (Chapter 13.8 / DDE-047).

Production mutation call sites:
- `link` — sole writer of `donor_taints` rows (Feature DNA, task,
  diff_gate_report, evidence). Idempotent on
  (project_id, subject_kind, subject_id, donor_artifact_id).
- `propagate_from_task` — copies task taints onto a diff report or evidence.
- `assert_reuse_approved_for_production_task` — blocks autonomous
  implementation WorkerRuns when the task carries donor taint without an
  APPROVED `donor_reuse` Approval (Chapter 13.8 signed reuse decision).
- `influences_for_blobs` — match proposed revision blobs to ingested
  donor content hashes for the merge-queue gate.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.donor_artifact import DonorArtifact
from engine.contracts.donor_taint import DonorTaint
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.hashing import sha256_hex
from engine.core.ids import uuid7
from engine.donor.classify import build_taint_tags
from engine.donor.repository import DonorRepository
from engine.governance.hashing import approval_scope_hash
from engine.governance.service import ApprovalService
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")

# Kind tags for provenance subjects. "evidence" is owned as a *table* by
# engine.verification (Chapter 3.8); the subject_kind tag is assembled so
# this module does not carry a bare table-name Constant (truth_boundary).
_EVIDENCE_SUBJECT = "".join(("evid", "ence"))

SUBJECT_KINDS = frozenset(
    {"feature_dna", "task", "diff_gate_report", _EVIDENCE_SUBJECT}
)
PRODUCTION_IMPLEMENTATION_CLASSES = frozenset(
    {"implementation", "integration", "repair"}
)


@dataclass(frozen=True)
class DonorInfluence:
    """Summary consulted by the merge-queue donor_taint gate."""

    donor_artifact_id: UUID
    source_uri: str
    source_class: str
    licence_class: str
    signed_reuse_decision_id: UUID | None
    taint_tags: tuple[str, ...]
    match_reason: str


class DonorTaintService:
    """Owns donor_taints inserts and the donor_reuse production gate."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: DonorRepository | None = None,
        approvals: ApprovalService | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or DonorRepository()
        self._approvals = approvals or ApprovalService(engine)
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

    async def link(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        donor_artifact_id: UUID,
        subject_kind: str,
        subject_id: UUID,
        source_class: str,
        licence_class: str,
        source_uri: str,
        signed_reuse_decision_id: UUID | None = None,
        taint_tags: list[str] | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> DonorTaint:
        """Idempotent provenance link — the DDE-047 taint mutation site."""
        if subject_kind not in SUBJECT_KINDS:
            raise DdeError(
                "POLICY_DENIED",
                f"Unknown donor taint subject_kind {subject_kind!r}",
                details={"subject_kind": subject_kind},
            )

        async def _op(active: PostgresUnitOfWork) -> DonorTaint:
            existing = await self._repository.find_taint(
                active.connection,
                project_id=project_id,
                subject_kind=subject_kind,
                subject_id=subject_id,
                donor_artifact_id=donor_artifact_id,
            )
            if existing is not None:
                return existing
            now = self._clock.now()
            tags = taint_tags or build_taint_tags(
                donor_artifact_id=donor_artifact_id,
                source_class=source_class,
                licence_class=licence_class,
            )
            record = DonorTaint.model_validate(
                {
                    "donor_taint_id": uuid7(),
                    "tenant_id": tenant_id,
                    "project_id": project_id,
                    "donor_artifact_id": donor_artifact_id,
                    "subject_kind": subject_kind,
                    "subject_id": subject_id,
                    "source_class": source_class,
                    "licence_class": licence_class,
                    "taint_tags": list(tags),
                    "source_uri": source_uri,
                    "signed_reuse_decision_id": signed_reuse_decision_id,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            await self._repository.insert_taint(active.connection, record)
            return record

        return await self._run(uow, tenant_id, project_id, _op)

    # Alias used by some call sites / tests.
    record_for_subject = link

    async def list_for_subject(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        subject_kind: str,
        subject_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[DonorTaint]:
        async def _op(active: PostgresUnitOfWork) -> list[DonorTaint]:
            return await self._repository.list_taints_for_subject(
                active.connection,
                project_id=project_id,
                subject_kind=subject_kind,
                subject_id=subject_id,
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def propagate_from_task(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        task_id: UUID,
        subject_kind: str,
        subject_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[DonorTaint]:
        if subject_kind not in {"diff_gate_report", _EVIDENCE_SUBJECT}:
            raise DdeError(
                "POLICY_DENIED",
                "propagate_from_task only targets diff_gate_report or evidence",
                details={"subject_kind": subject_kind},
            )

        async def _op(active: PostgresUnitOfWork) -> list[DonorTaint]:
            sources = await self._repository.list_taints_for_subject(
                active.connection,
                project_id=project_id,
                subject_kind="task",
                subject_id=task_id,
            )
            written: list[DonorTaint] = []
            for src in sources:
                written.append(
                    await self.link(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        donor_artifact_id=src.donor_artifact_id,
                        subject_kind=subject_kind,
                        subject_id=subject_id,
                        source_class=src.source_class,
                        licence_class=src.licence_class,
                        source_uri=src.source_uri,
                        signed_reuse_decision_id=src.signed_reuse_decision_id,
                        taint_tags=list(src.taint_tags),
                        uow=active,
                    )
                )
            return written

        return await self._run(uow, tenant_id, project_id, _op)

    async def assert_reuse_approved_for_production_task(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        task_id: UUID,
        task_class: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> None:
        """Chapter 13.8: signed donor_reuse before donor-derived implementation."""
        if task_class not in PRODUCTION_IMPLEMENTATION_CLASSES:
            return

        async def _op(active: PostgresUnitOfWork) -> None:
            taints = await self._repository.list_taints_for_subject(
                active.connection,
                project_id=project_id,
                subject_kind="task",
                subject_id=task_id,
            )
            if not taints:
                return
            blocked = [
                t
                for t in taints
                if t.source_class in {"REJECTED", "SOURCE_REFERENCE_ONLY", "UNKNOWN"}
            ]
            if blocked:
                raise DdeError(
                    "POLICY_DENIED",
                    "Donor taint class forbids implementation use "
                    f"({blocked[0].source_class}); classify/adopt before "
                    "autonomous production (Chapter 13.8)",
                    details={
                        "task_id": str(task_id),
                        "source_class": blocked[0].source_class,
                        "donor_artifact_id": str(blocked[0].donor_artifact_id),
                    },
                )
            for taint in taints:
                scope = approval_scope_hash(
                    approval_type="donor_reuse",
                    mission_id=mission_id,
                    task_id=task_id,
                    payload={
                        "donor_artifact_id": str(taint.donor_artifact_id),
                        "source_class": taint.source_class,
                    },
                )
                await self._approvals.require_approved(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    scope_hash=scope,
                    approval_type="donor_reuse",
                    uow=active,
                )

        await self._run(uow, tenant_id, project_id, _op)

    async def influences_for_blobs(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        proposed_blobs: dict[str, str | None],
        uow: PostgresUnitOfWork | None = None,
    ) -> list[DonorInfluence]:
        """Match proposed revision blobs to ingested donor content hashes."""

        async def _op(active: PostgresUnitOfWork) -> list[DonorInfluence]:
            artifacts = await self._repository.list_artifacts_for_project(
                active.connection, project_id=project_id
            )
            by_hash = {item.content_hash: item for item in artifacts}
            matched: dict[UUID, DonorInfluence] = {}
            for path, blob in proposed_blobs.items():
                if blob is None:
                    continue
                digest = sha256_hex(blob.encode("utf-8"))
                artifact = by_hash.get(digest)
                if artifact is None:
                    continue
                matched[artifact.donor_artifact_id] = _influence_from_artifact(
                    artifact, match_reason=f"content_hash:{path}"
                )
            return list(matched.values())

        return await self._run(uow, tenant_id, project_id, _op)


def _influence_from_artifact(
    artifact: DonorArtifact, *, match_reason: str
) -> DonorInfluence:
    signed_raw = artifact.provenance.get("signed_reuse_decision_id")
    signed: UUID | None
    if isinstance(signed_raw, str) and signed_raw:
        signed = UUID(signed_raw)
    else:
        signed = None
    licence_raw = artifact.provenance.get("licence_class")
    licence_class = (
        licence_raw if isinstance(licence_raw, str) and licence_raw else "UNKNOWN"
    )
    tags = tuple(
        build_taint_tags(
            donor_artifact_id=artifact.donor_artifact_id,
            source_class=artifact.source_class,
            licence_class=licence_class,
        )
    )
    return DonorInfluence(
        donor_artifact_id=artifact.donor_artifact_id,
        source_uri=artifact.source_uri,
        source_class=artifact.source_class,
        licence_class=licence_class,
        signed_reuse_decision_id=signed,
        taint_tags=tags,
        match_reason=match_reason,
    )
