"""DDE-069 lock service.

Sole writer of `frontend_locks`. Locks are created and released through
here so every mutation path consults the same set, and so a release is a
recorded act with an actor rather than a row disappearing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from engine.contracts.frontend_lock import FrontendLock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.studio.locks.resolution import GLOBAL_SCOPE, LOCK_COVERAGE
from engine.studio.pxg.service import validate_key
from engine.studio.tables import frontend_locks
from engine.truth.db import open_unit_of_work


class LockService:
    """Creates, releases and reads frontend locks."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def create(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        lock_kind: str,
        scope_key: str,
        reason: str,
        created_by: UUID,
    ) -> FrontendLock:
        if lock_kind not in LOCK_COVERAGE:
            raise DdeError(
                "VALIDATION_FAILED",
                "unknown lock kind",
                retryable=False,
                details={"lock_kind": lock_kind, "known": sorted(LOCK_COVERAGE)},
            )
        if scope_key != GLOBAL_SCOPE:
            validate_key(scope_key)
        if not reason.strip():
            raise DdeError(
                "VALIDATION_FAILED",
                "a lock must record why it exists; an unexplained lock is "
                "indistinguishable from a mistake",
                retryable=False,
                details={"scope_key": scope_key},
            )
        now = datetime.now(UTC)
        record = FrontendLock(
            lock_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            lock_kind=lock_kind,
            scope_key=scope_key,
            status="ACTIVE",
            reason=reason,
            created_by=created_by,
            released_by=None,
            released_at=None,
            lock_version=1,
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            await uow.connection.execute(
                frontend_locks.insert().values(**record.model_dump())
            )
            await uow.commit()
        return record

    async def release(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        lock_id: UUID,
        released_by: UUID,
    ) -> FrontendLock:
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                update(frontend_locks)
                .where(
                    frontend_locks.c.lock_id == lock_id,
                    frontend_locks.c.tenant_id == tenant_id,
                    frontend_locks.c.project_id == project_id,
                    frontend_locks.c.status == "ACTIVE",
                )
                .values(
                    status="RELEASED",
                    released_by=released_by,
                    released_at=now,
                    updated_at=now,
                    lock_version=frontend_locks.c.lock_version + 1,
                )
                .returning(frontend_locks)
            )
            row = result.mappings().first()
            if row is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "no active lock with that id in this project",
                    retryable=False,
                    details={"lock_id": str(lock_id)},
                )
            await uow.commit()
        return FrontendLock.model_validate(dict(row))

    async def active(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> tuple[FrontendLock, ...]:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            return await self.active_on(
                uow.connection, tenant_id=tenant_id, project_id=project_id
            )

    async def active_on(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        project_id: UUID,
    ) -> tuple[FrontendLock, ...]:
        """Read the active set on a caller's open unit of work, so a
        mutation can check locks inside the same transaction it writes in."""
        result = await connection.execute(
            select(frontend_locks)
            .where(
                frontend_locks.c.tenant_id == tenant_id,
                frontend_locks.c.project_id == project_id,
                frontend_locks.c.status == "ACTIVE",
            )
            .order_by(frontend_locks.c.scope_key, frontend_locks.c.lock_kind)
        )
        return tuple(
            FrontendLock.model_validate(dict(row)) for row in result.mappings().all()
        )

    async def inventory(self, *, tenant_id: UUID, project_id: UUID) -> dict[str, int]:
        """Counts per lock kind for the golden explorer's Locks group."""
        locks = await self.active(tenant_id=tenant_id, project_id=project_id)
        counts: dict[str, int] = {kind: 0 for kind in LOCK_COVERAGE}
        for lock in locks:
            counts[lock.lock_kind] += 1
        return counts
