"""Chapter 17.5 WORM: evidence rows and evidence-linked object keys cannot
be deleted during the retention window.

`WormRetentionService.purge_evidence` is the production mutation that
would delete an evidence row — it always refuses. `ArtifactObjectStore.delete`
is the object-layer half (see `engine.object_store.scope`).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.core.errors import DdeError
from engine.object_store.scope import WORM_CONTROL
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work
from engine.verification.repository import EvidenceRepository


class WormRetentionService:
    """Sole public purge path for `evidence` rows (Chapter 17.5)."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: EvidenceRepository | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or EvidenceRepository()

    async def purge_evidence(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        evidence_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> None:
        """Refuse deletion of an evidence row. A new idempotency key or a
        second caller cannot bypass this: there is no SQL DELETE on this
        path."""

        async def _op(active: PostgresUnitOfWork) -> None:
            record = await self._repository.get_evidence(active.connection, evidence_id)
            if record is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "Unknown evidence row",
                    details={"evidence_id": str(evidence_id), "control": WORM_CONTROL},
                )
            if record.tenant_id != tenant_id or record.project_id != project_id:
                raise DdeError(
                    "POLICY_DENIED",
                    "Evidence tenant/project does not match the purge request",
                    details={"evidence_id": str(evidence_id), "control": WORM_CONTROL},
                )
            raise DdeError(
                "POLICY_DENIED",
                "WORM: evidence cannot be deleted during the retention window",
                retryable=False,
                details={
                    "evidence_id": str(evidence_id),
                    "control": WORM_CONTROL,
                    "content_hash": record.content_hash,
                },
            )

        if uow is not None:
            await _op(uow)
            return
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as owned:
            await _op(owned)
            await owned.commit()
