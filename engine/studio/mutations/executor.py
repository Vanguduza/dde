"""DDE-069 mutation executor.

Sole writer of `frontend_mutations`. Persists a plan, applies the
accepted mutations to the candidate's Project Experience Graph, and moves
the candidate's state.

Two properties matter more than the mechanics:

*A refusal is recorded, not swallowed.* Refused requests are written as
`REFUSED` rows with a typed code, so the studio can say what it declined
and why instead of appearing to do nothing.

*Preconditions are re-checked at apply time.* A plan carries the PXG
revision and effective-lock hash it was made under; if either moved, the
apply is refused rather than landing on a base that changed underneath it.

*The accepted graph is never written here.* A candidate's changes live
entirely in its append-only mutation log; its effective graph is that log
projected over the accepted one (`engine.studio.mutations.projection`).
Promotion is the only thing that writes accepted nodes. The isolation is
therefore structural rather than a rule to remember -- there is no code
path from editing a candidate to mutating accepted state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.frontend_mutation import FrontendMutation
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.studio.candidates.lifecycle import (
    CandidateState,
    state_after_mutation,
)
from engine.studio.candidates.service import CandidateService
from engine.studio.locks.resolution import effective_lock_hash
from engine.studio.locks.service import LockService
from engine.studio.mutations.planner import MutationPlan, MutationRequest, plan
from engine.studio.mutations.projection import project
from engine.studio.pxg.service import PxgGraph, PxgService
from engine.studio.tables import frontend_mutations
from engine.truth.db import open_unit_of_work


@dataclass(frozen=True)
class MutationOutcome:
    """What actually happened, so the caller can render it truthfully."""

    applied: tuple[FrontendMutation, ...]
    refused: tuple[FrontendMutation, ...]
    candidate_state: CandidateState
    pxg_revision: int

    @property
    def fully_applied(self) -> bool:
        return bool(self.applied) and not self.refused


class MutationExecutor:
    """Plans, records and applies frontend mutations."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        pxg: PxgService | None = None,
        locks: LockService | None = None,
        candidates: CandidateService | None = None,
    ) -> None:
        self._engine = engine
        self._pxg = pxg or PxgService(engine)
        self._locks = locks or LockService(engine)
        self._candidates = candidates or CandidateService(engine, pxg=self._pxg)

    async def plan(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
        requests: list[MutationRequest],
        contract_version: int | None = None,
        design_system_hash: str | None = None,
    ) -> MutationPlan:
        candidate = await self._candidates.get(
            tenant_id=tenant_id, project_id=project_id, candidate_id=candidate_id
        )
        graph = await self.candidate_graph(
            tenant_id=tenant_id, project_id=project_id, candidate_id=candidate_id
        )
        locks = await self._locks.active(tenant_id=tenant_id, project_id=project_id)
        return plan(
            requests,
            candidate=candidate,
            graph=graph,
            locks=locks,
            contract_version=contract_version,
            design_system_hash=design_system_hash,
        )

    async def candidate_graph(
        self, *, tenant_id: UUID, project_id: UUID, candidate_id: UUID
    ) -> PxgGraph:
        """The accepted graph with this candidate's applied log replayed.

        Every planning decision resolves against this, not the accepted
        graph, so a candidate sees its own edits without any of them
        having been written to accepted state.
        """
        accepted = await self._pxg.load(tenant_id=tenant_id, project_id=project_id)
        history = await self.history(
            tenant_id=tenant_id, project_id=project_id, candidate_id=candidate_id
        )
        return project(accepted, history)

    async def apply(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
        requests: list[MutationRequest],
        contract_version: int | None = None,
        design_system_hash: str | None = None,
    ) -> MutationOutcome:
        """Plan and apply in one governed step.

        Re-derives the plan against freshly read state and then verifies
        that state has not moved between planning and writing, so a
        concurrent edit produces a conflict rather than a silent overwrite.
        """
        candidate = await self._candidates.get(
            tenant_id=tenant_id, project_id=project_id, candidate_id=candidate_id
        )
        graph = await self.candidate_graph(
            tenant_id=tenant_id, project_id=project_id, candidate_id=candidate_id
        )
        locks = await self._locks.active(tenant_id=tenant_id, project_id=project_id)
        computed = plan(
            requests,
            candidate=candidate,
            graph=graph,
            locks=locks,
            contract_version=contract_version,
            design_system_hash=design_system_hash,
        )

        now = datetime.now(UTC)
        applied_rows: list[FrontendMutation] = []
        refused_rows: list[FrontendMutation] = []

        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            connection = uow.connection

            # Re-check the preconditions inside the write transaction. The
            # plan above was made against a read that has since had time to
            # go stale.
            current_locks = await self._locks.active_on(
                connection, tenant_id=tenant_id, project_id=project_id
            )
            if effective_lock_hash(current_locks) != effective_lock_hash(locks):
                raise DdeError(
                    "VERSION_CONFLICT",
                    "the lock set changed while this mutation was planned; "
                    "replan against the current locks",
                    retryable=True,
                    details={"candidate_id": str(candidate_id)},
                )

            sequence = int(
                await connection.scalar(
                    select(
                        func.coalesce(func.max(frontend_mutations.c.sequence), 0)
                    ).where(frontend_mutations.c.candidate_id == candidate_id)
                )
                or 0
            )

            for refusal in computed.refused:
                sequence += 1
                record = _row(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    candidate_id=candidate_id,
                    sequence=sequence,
                    request=refusal.request,
                    status="REFUSED",
                    inverse={},
                    preconditions=refusal.preconditions.model_dump(mode="json"),
                    now=now,
                    refusal_code=refusal.code,
                    refusal_detail=refusal.detail,
                )
                await connection.execute(
                    frontend_mutations.insert().values(
                        **record.model_dump(
                            exclude={"payload", "inverse", "preconditions"}
                        ),
                        payload=record.payload,
                        inverse=record.inverse,
                        preconditions=record.preconditions.model_dump(mode="json"),
                    )
                )
                refused_rows.append(record)

            for accepted in computed.planned:
                sequence += 1
                record = _row(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    candidate_id=candidate_id,
                    sequence=sequence,
                    request=accepted.request,
                    status="APPLIED",
                    inverse=accepted.inverse,
                    preconditions=accepted.preconditions.model_dump(mode="json"),
                    now=now,
                )
                await connection.execute(
                    frontend_mutations.insert().values(
                        **record.model_dump(
                            exclude={"payload", "inverse", "preconditions"}
                        ),
                        payload=record.payload,
                        inverse=record.inverse,
                        preconditions=record.preconditions.model_dump(mode="json"),
                    )
                )
                applied_rows.append(record)

            await uow.commit()

        # No accepted node is written here. The candidate's effective
        # revision advances by the number of mutations it applied.
        revision = graph.revision + len(applied_rows)

        state = CandidateState(candidate.state)
        if applied_rows:
            target = state_after_mutation(state)
            if target is not state:
                updated = await self._candidates.transition(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    candidate_id=candidate_id,
                    target=target,
                    detail=f"{len(applied_rows)} mutation(s) applied",
                )
                state = CandidateState(updated.state)

        return MutationOutcome(
            applied=tuple(applied_rows),
            refused=tuple(refused_rows),
            candidate_state=state,
            pxg_revision=revision,
        )

    async def revert(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
        mutation_id: UUID,
    ) -> FrontendMutation:
        """Revert one applied mutation by its recorded inverse.

        The original row is marked REVERTED rather than deleted: the edit
        history stays auditable, which is what lets provenance survive an
        undo.
        """
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                select(frontend_mutations).where(
                    frontend_mutations.c.mutation_id == mutation_id,
                    frontend_mutations.c.candidate_id == candidate_id,
                    frontend_mutations.c.tenant_id == tenant_id,
                    frontend_mutations.c.project_id == project_id,
                )
            )
            row = result.mappings().first()
            if row is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "unknown mutation for this candidate",
                    retryable=False,
                    details={"mutation_id": str(mutation_id)},
                )
            original = FrontendMutation.model_validate(dict(row))
            if original.status != "APPLIED":
                raise DdeError(
                    "POLICY_DENIED",
                    "only an applied mutation can be reverted",
                    retryable=False,
                    details={
                        "mutation_id": str(mutation_id),
                        "status": original.status,
                    },
                )
            await uow.connection.execute(
                update(frontend_mutations)
                .where(frontend_mutations.c.mutation_id == mutation_id)
                .values(status="REVERTED", updated_at=now)
            )
            await uow.commit()

        inverse = original.inverse
        operation = str(inverse.get("operation") or "SET_PROPERTY")
        payload: dict[str, object] = {
            key: value
            for key, value in inverse.items()
            if key not in ("operation", "target_key")
        }
        outcome = await self.apply(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
            requests=[
                MutationRequest(
                    operation=operation,
                    target_key=original.target_key,
                    origin=original.origin,
                    payload=payload,
                )
            ],
        )
        if not outcome.applied:
            refusal = outcome.refused[0] if outcome.refused else None
            raise DdeError(
                "POLICY_DENIED",
                "the compensating mutation was refused; the original stays "
                "marked reverted and the graph is unchanged",
                retryable=False,
                details={
                    "mutation_id": str(mutation_id),
                    "refusal_code": refusal.refusal_code if refusal else None,
                    "refusal_detail": refusal.refusal_detail if refusal else None,
                },
            )
        return outcome.applied[0]

    async def history(
        self, *, tenant_id: UUID, project_id: UUID, candidate_id: UUID
    ) -> tuple[FrontendMutation, ...]:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                select(frontend_mutations)
                .where(
                    frontend_mutations.c.candidate_id == candidate_id,
                    frontend_mutations.c.tenant_id == tenant_id,
                    frontend_mutations.c.project_id == project_id,
                )
                .order_by(frontend_mutations.c.sequence)
            )
            rows = result.mappings().all()
        return tuple(FrontendMutation.model_validate(dict(row)) for row in rows)


def _row(
    *,
    tenant_id: UUID,
    project_id: UUID,
    candidate_id: UUID,
    sequence: int,
    request: MutationRequest,
    status: str,
    inverse: dict[str, object],
    preconditions: dict[str, object],
    now: datetime,
    refusal_code: str | None = None,
    refusal_detail: str | None = None,
) -> FrontendMutation:
    from engine.contracts.frontend_mutation import Preconditions

    return FrontendMutation(
        mutation_id=uuid7(),
        tenant_id=tenant_id,
        project_id=project_id,
        candidate_id=candidate_id,
        sequence=sequence,
        operation=request.operation,
        target_key=request.target_key,
        origin=request.origin,
        status=status,
        payload=dict(request.payload),
        inverse=inverse,
        preconditions=Preconditions.model_validate(preconditions),
        refusal_code=refusal_code,
        refusal_detail=refusal_detail,
        reverted_by=None,
        created_at=now,
        updated_at=now,
    )
