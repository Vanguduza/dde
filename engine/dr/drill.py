"""Chapter 17.5 control-plane drill: chain verification, WORM hold,
isolated restore, and emergency revoke.

A drill that is not executed counts as a failed control. `run()` is the
production caller of `AuditService.verify_chain`,
`WormRetentionService.purge_evidence`, `ArtifactObjectStore.delete`,
`IsolatedRestoreService.restore_tenant`, and
`CredentialBrokerService.emergency_revoke`.

PostgreSQL PITR/WAL archiving, R2 object-lock, and event-archive export
are inspected or named on the DDE-062 chapter gate (EDR-0033) — they are
not claimed here. Redis is not read; it is disposable (Ch.17.5 / 17.6).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.audit.service import AuditService
from engine.capabilities.broker.service import CredentialBrokerService
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.dr.restore import IsolatedRestoreResult, IsolatedRestoreService
from engine.dr.worm import WormRetentionService
from engine.object_store.scope import (
    WORM_CONTROL,
    ArtifactObjectStore,
    storage_key_for_artifact,
)


@dataclass(frozen=True)
class DrillResult:
    chain_verified: bool
    worm_held: bool
    object_worm_held: bool
    restore: IsolatedRestoreResult
    emergency_revoke_count: int


class ControlPlaneDrill:
    """Executable Chapter 17.5 drill against live PostgreSQL."""

    def __init__(
        self,
        engine: AsyncEngine,
        audit: AuditService | None = None,
        worm: WormRetentionService | None = None,
        objects: ArtifactObjectStore | None = None,
        restore: IsolatedRestoreService | None = None,
        broker: CredentialBrokerService | None = None,
    ) -> None:
        self._engine = engine
        self._audit = audit or AuditService(engine)
        self._worm = worm or WormRetentionService(engine)
        self._objects = objects or ArtifactObjectStore()
        self._restore = restore or IsolatedRestoreService(engine)
        self._broker = broker or CredentialBrokerService(engine)

    async def run(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
    ) -> DrillResult:
        await self._audit.append(
            tenant_id=tenant_id,
            project_id=project_id,
            event_type="drill.started",
            payload={"chapter": "17.5"},
        )
        await self._audit.verify_chain(tenant_id=tenant_id)
        worm_held = await self._assert_worm_purge_refused(
            tenant_id=tenant_id, project_id=project_id
        )
        object_worm_held = self._assert_object_delete_refused(
            tenant_id=tenant_id, project_id=project_id
        )
        restore = await self._restore.restore_tenant(
            tenant_id=tenant_id, project_id=project_id
        )
        revoked = await self._broker.emergency_revoke(
            tenant_id=tenant_id,
            project_id=project_id,
            reason="ch17.5-drill",
        )
        await self._audit.append(
            tenant_id=tenant_id,
            project_id=project_id,
            event_type="drill.completed",
            payload={
                "scratch_database": restore.scratch_database,
                "audit_events_restored": restore.audit_events_restored,
                "pitr_archive_mode": restore.pitr.archive_mode,
            },
        )
        return DrillResult(
            chain_verified=True,
            worm_held=worm_held,
            object_worm_held=object_worm_held,
            restore=restore,
            emergency_revoke_count=len(revoked),
        )

    async def _assert_worm_purge_refused(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> bool:
        try:
            await self._worm.purge_evidence(
                tenant_id=tenant_id,
                project_id=project_id,
                evidence_id=uuid7(),
            )
        except DdeError as exc:
            if exc.error_code != "POLICY_DENIED":
                raise
            if exc.details is None or exc.details.get("control") != WORM_CONTROL:
                raise
            return True
        raise DdeError(
            "POLICY_DENIED",
            "WORM drill failed: evidence purge was permitted",
            details={"control": WORM_CONTROL},
        )

    def _assert_object_delete_refused(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> bool:
        key = storage_key_for_artifact(
            tenant_id=tenant_id, project_id=project_id, content_hash="drill"
        )
        try:
            self._objects.delete(
                tenant_id=tenant_id,
                project_id=project_id,
                key=key,
                evidence_linked=True,
            )
        except DdeError as exc:
            if exc.error_code != "POLICY_DENIED":
                raise
            if exc.details is None or exc.details.get("control") != WORM_CONTROL:
                raise
            return True
        raise DdeError(
            "POLICY_DENIED",
            "WORM drill failed: evidence-linked object delete was permitted",
            details={"control": WORM_CONTROL},
        )
