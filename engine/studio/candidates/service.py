"""DDE-069 candidate service.

Sole writer of `frontend_candidates`. The accepted design is never edited
in place: exploratory work happens on a candidate branched from an
accepted PXG revision, and promotion creates the next accepted revision.

Staleness is the reason `base_pxg_revision` is recorded. When the
accepted base moves past a candidate's base, the candidate describes a
project that no longer exists; it is reported stale and the promotion
gate refuses it rather than applying it over whatever changed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from engine.contracts.frontend_candidate import FrontendCandidate
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.studio.candidates.lifecycle import (
    CandidateState,
    assert_transition,
)
from engine.studio.pxg.service import PxgService, validate_key
from engine.studio.tables import frontend_candidates
from engine.truth.db import open_unit_of_work


@dataclass(frozen=True)
class CandidateView:
    """A candidate plus the derived facts the strip must show honestly."""

    candidate: FrontendCandidate
    current_pxg_revision: int
    stale: bool

    @property
    def state(self) -> CandidateState:
        return CandidateState(self.candidate.state)


class CandidateService:
    """Creates and transitions isolated frontend candidates."""

    def __init__(self, engine: AsyncEngine, *, pxg: PxgService | None = None) -> None:
        self._engine = engine
        self._pxg = pxg or PxgService(engine)

    async def create(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        title: str,
        origin: str,
        scope_keys: Sequence[str],
        mission_id: UUID | None = None,
        base_contract_version: int | None = None,
        provenance: dict[str, object] | None = None,
    ) -> FrontendCandidate:
        if not scope_keys:
            raise DdeError(
                "VALIDATION_FAILED",
                "a candidate must declare the PXG keys it may mutate; an "
                "unscoped candidate cannot be checked for conflicts",
                retryable=False,
            )
        for key in scope_keys:
            validate_key(key)
        base_revision = await self._pxg.current_revision(
            tenant_id=tenant_id, project_id=project_id
        )
        now = datetime.now(UTC)
        record = FrontendCandidate(
            candidate_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            workspace_id=None,
            title=title,
            state=CandidateState.REQUESTED.value,
            origin=origin,
            base_pxg_revision=base_revision,
            base_contract_version=base_contract_version,
            scope_keys=list(scope_keys),
            verification_run_id=None,
            provenance=provenance or {},
            state_detail=None,
            superseded_by=None,
            promoted_at=None,
            lock_version=1,
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            await uow.connection.execute(
                frontend_candidates.insert().values(
                    **record.model_dump(exclude={"scope_keys", "provenance"}),
                    scope_keys=list(scope_keys),
                    provenance=provenance or {},
                )
            )
            await uow.commit()
        return record

    async def get(
        self, *, tenant_id: UUID, project_id: UUID, candidate_id: UUID
    ) -> FrontendCandidate:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            return await self.get_on(
                uow.connection,
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=candidate_id,
            )

    async def get_on(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
    ) -> FrontendCandidate:
        result = await connection.execute(
            select(frontend_candidates).where(
                frontend_candidates.c.candidate_id == candidate_id,
                frontend_candidates.c.tenant_id == tenant_id,
                frontend_candidates.c.project_id == project_id,
            )
        )
        row = result.mappings().first()
        if row is None:
            raise DdeError(
                "POLICY_DENIED",
                "unknown candidate in this project",
                retryable=False,
                details={"candidate_id": str(candidate_id)},
            )
        return FrontendCandidate.model_validate(dict(row))

    async def transition(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
        target: CandidateState,
        detail: str | None = None,
        workspace_id: UUID | None = None,
        verification_run_id: UUID | None = None,
        superseded_by: UUID | None = None,
    ) -> FrontendCandidate:
        """Move a candidate, refusing anything the lifecycle table forbids."""
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            current = await self.get_on(
                uow.connection,
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=candidate_id,
            )
            assert_transition(CandidateState(current.state), target)

            values: dict[str, object] = {
                "state": target.value,
                "state_detail": detail,
                "updated_at": now,
                "lock_version": frontend_candidates.c.lock_version + 1,
            }
            if workspace_id is not None:
                values["workspace_id"] = workspace_id
            if target is CandidateState.DIRTY:
                # A verdict describes the code before the edit. Keeping its
                # run id attached after a mutation would let downstream reads
                # mistake stale evidence for current evidence.
                values["verification_run_id"] = None
            elif verification_run_id is not None:
                values["verification_run_id"] = verification_run_id
            if superseded_by is not None:
                values["superseded_by"] = superseded_by
            if target is CandidateState.PROMOTED:
                values["promoted_at"] = now

            result = await uow.connection.execute(
                update(frontend_candidates)
                .where(
                    frontend_candidates.c.candidate_id == candidate_id,
                    # Optimistic lock: a concurrent transition that already
                    # moved this candidate must lose rather than overwrite.
                    frontend_candidates.c.lock_version == current.lock_version,
                )
                .values(**values)
                .returning(frontend_candidates)
            )
            row = result.mappings().first()
            if row is None:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "candidate changed concurrently; re-read and retry",
                    retryable=True,
                    details={"candidate_id": str(candidate_id)},
                )
            await uow.commit()
        return FrontendCandidate.model_validate(dict(row))

    async def view(
        self, *, tenant_id: UUID, project_id: UUID, candidate_id: UUID
    ) -> CandidateView:
        candidate = await self.get(
            tenant_id=tenant_id, project_id=project_id, candidate_id=candidate_id
        )
        current = await self._pxg.current_revision(
            tenant_id=tenant_id, project_id=project_id
        )
        return CandidateView(
            candidate=candidate,
            current_pxg_revision=current,
            stale=candidate.base_pxg_revision < current,
        )

    async def board(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> tuple[CandidateView, ...]:
        """What the candidate strip renders. Staleness is computed once
        against the current revision rather than per card."""
        current = await self._pxg.current_revision(
            tenant_id=tenant_id, project_id=project_id
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                select(frontend_candidates)
                .where(
                    frontend_candidates.c.tenant_id == tenant_id,
                    frontend_candidates.c.project_id == project_id,
                )
                .order_by(frontend_candidates.c.created_at.desc())
            )
            rows = result.mappings().all()
        return tuple(
            CandidateView(
                candidate=FrontendCandidate.model_validate(dict(row)),
                current_pxg_revision=current,
                stale=int(row["base_pxg_revision"]) < current,
            )
            for row in rows
        )
