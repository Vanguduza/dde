"""Chapter 5.13 eval corpus construction protocol.

**Sourcing (point 1).** `build_case_from_integration` refuses any
`IntegrationProposal` that is not `MERGED` -- an eval case must come from
a real, accepted change, never a synthetic one.

**Ground truth (point 2).** `required_refs` is derived mechanically from
the accepted diff's `changed_paths` plus the source Task's
`requirement_refs` -- exactly the "every file... the accepted change
actually touched or depended on" rule, with no human guess involved at
case-construction time.

**Human review + freeze (point 3).** A case is born `draft`. Only
`freeze_case` -- an explicit, separate call a human/reviewer triggers --
moves it to `frozen` and sets `frozen_version`. `PromotionGateService`
never reads `draft` rows; only `frozen` cases form the corpus a
promotion decision can be based on.

**Never deleted, only retired (point 5).** `retire_case` is the only
terminal transition this module exposes; there is no delete method.

Corpus growth from production missions (point 5's "corpus grows from
production") and the minimum-size/diversity check (point 4: 60 cases,
6 task classes, 10 adversarial) are enforced by
`engine.context.promotion.corpus_adequacy`, not here -- this module only
owns the case lifecycle.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.context.eval_repository import EvalCaseRepository
from engine.contracts.eval_case import EvalCase
from engine.core.clock import Clock, SystemClock
from engine.core.ids import uuid7
from engine.integration.repository import IntegrationProposalRepository
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")


class EvalCorpusService:
    """Async, PostgreSQL-backed writer for `eval_cases` (Chapter 3.8)."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: EvalCaseRepository | None = None,
        proposals: IntegrationProposalRepository | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or EvalCaseRepository()
        self._proposals = proposals or IntegrationProposalRepository()
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
            result = await body(owned)
            await owned.commit()
            return result

    async def build_case_from_integration(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        source_proposal_id: UUID,
        source_mission_id: UUID,
        source_task_id: UUID,
        task_class: str,
        task_requirement_refs: list[str],
        is_adversarial: bool = False,
        uow: PostgresUnitOfWork | None = None,
    ) -> EvalCase:
        async def _op(active: PostgresUnitOfWork) -> EvalCase:
            proposal = await self._proposals.get_proposal(
                active.connection, source_proposal_id
            )
            if proposal is None:
                raise ValueError(f"no integration proposal {source_proposal_id}")
            if proposal.status != "MERGED":
                raise ValueError(
                    "Chapter 5.13 eval cases must be sourced from a real, "
                    f"accepted (MERGED) diff; proposal {source_proposal_id} "
                    f"has status {proposal.status}"
                )
            required_refs = sorted(
                set(proposal.changed_paths) | set(task_requirement_refs)
            )
            now = self._clock.now()
            case = EvalCase(
                eval_case_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                source_mission_id=source_mission_id,
                source_task_id=source_task_id,
                source_proposal_id=source_proposal_id,
                task_class=task_class,
                is_adversarial=is_adversarial,
                required_refs=required_refs,
                status="draft",
                frozen_version=None,
                retired_reason=None,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_case(active.connection, case)
            return case

        return await self._run(uow, tenant_id, project_id, _op)

    async def freeze_case(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        eval_case_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> EvalCase:
        async def _op(active: PostgresUnitOfWork) -> EvalCase:
            case = await self._repository.get_case(active.connection, eval_case_id)
            if case is None:
                raise ValueError(f"no eval case {eval_case_id}")
            if case.status != "draft":
                raise ValueError(
                    f"eval case {eval_case_id} is {case.status}, not draft; "
                    "only a draft case may be frozen"
                )
            now = self._clock.now()
            await self._repository.update_case(
                active.connection,
                eval_case_id,
                fields={"status": "frozen", "frozen_version": 1, "updated_at": now},
            )
            reloaded = await self._repository.get_case(active.connection, eval_case_id)
            if reloaded is None:
                raise RuntimeError(f"eval case {eval_case_id} vanished mid-transaction")
            return reloaded

        return await self._run(uow, tenant_id, project_id, _op)

    async def retire_case(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        eval_case_id: UUID,
        reason: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> EvalCase:
        if not reason.strip():
            raise ValueError("retiring an eval case requires a non-empty reason")

        async def _op(active: PostgresUnitOfWork) -> EvalCase:
            case = await self._repository.get_case(active.connection, eval_case_id)
            if case is None:
                raise ValueError(f"no eval case {eval_case_id}")
            if case.status == "retired":
                return case
            now = self._clock.now()
            await self._repository.update_case(
                active.connection,
                eval_case_id,
                fields={
                    "status": "retired",
                    "retired_reason": reason,
                    "updated_at": now,
                },
            )
            reloaded = await self._repository.get_case(active.connection, eval_case_id)
            if reloaded is None:
                raise RuntimeError(f"eval case {eval_case_id} vanished mid-transaction")
            return reloaded

        return await self._run(uow, tenant_id, project_id, _op)

    async def list_active_corpus(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[EvalCase]:
        async def _op(active: PostgresUnitOfWork) -> list[EvalCase]:
            return await self._repository.list_frozen_corpus(
                active.connection, tenant_id, project_id
            )

        return await self._run(uow, tenant_id, project_id, _op)
