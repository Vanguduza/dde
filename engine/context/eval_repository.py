"""Async repositories for `eval_cases` and `promotion_gate_runs` (Chapter
3.3, 3.8, 5.13) -- both owned by `engine.context`.

Every read and write here executes on the connection of an already-open
unit of work (Chapter 3.5); this module never begins or ends a
transaction itself.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.context.eval_tables import eval_cases, promotion_gate_runs
from engine.contracts.eval_case import EvalCase
from engine.contracts.promotion_gate_run import PromotionGateRun


class EvalCaseRepository:
    """Reads and writes rows for `eval_cases` -- the Chapter 5.13 eval
    corpus. Cases are never deleted (Chapter 5.13: "cases are never
    deleted, only retired with reason"); this repository exposes no
    delete method."""

    async def insert_case(self, connection: AsyncConnection, record: EvalCase) -> None:
        dumped = record.model_dump()
        dumped["required_refs"] = list(dumped["required_refs"])
        await connection.execute(eval_cases.insert().values(**dumped))

    async def get_case(
        self, connection: AsyncConnection, eval_case_id: UUID
    ) -> EvalCase | None:
        result = await connection.execute(
            select(eval_cases).where(eval_cases.c.eval_case_id == eval_case_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return EvalCase.model_validate(dict(row))

    async def update_case(
        self,
        connection: AsyncConnection,
        eval_case_id: UUID,
        *,
        fields: dict[str, object],
    ) -> int:
        result = await connection.execute(
            eval_cases.update()
            .where(eval_cases.c.eval_case_id == eval_case_id)
            .values(**fields)
        )
        return int(result.rowcount)

    async def list_frozen_corpus(
        self, connection: AsyncConnection, tenant_id: UUID, project_id: UUID
    ) -> list[EvalCase]:
        """The active corpus for promotion evaluation: `frozen` cases only
        -- `draft` cases have not cleared the Chapter 5.13 human-review
        step, and `retired` cases are excluded but never removed."""
        result = await connection.execute(
            select(eval_cases)
            .where(
                eval_cases.c.tenant_id == tenant_id,
                eval_cases.c.project_id == project_id,
                eval_cases.c.status == "frozen",
            )
            .order_by(eval_cases.c.created_at.asc())
        )
        return [EvalCase.model_validate(dict(row)) for row in result.mappings().all()]

    async def list_for_project(
        self, connection: AsyncConnection, tenant_id: UUID, project_id: UUID
    ) -> list[EvalCase]:
        result = await connection.execute(
            select(eval_cases)
            .where(
                eval_cases.c.tenant_id == tenant_id,
                eval_cases.c.project_id == project_id,
            )
            .order_by(eval_cases.c.created_at.asc())
        )
        return [EvalCase.model_validate(dict(row)) for row in result.mappings().all()]


class PromotionGateRunRepository:
    """Reads and writes rows for `promotion_gate_runs`."""

    async def insert_run(
        self, connection: AsyncConnection, record: PromotionGateRun
    ) -> None:
        await connection.execute(
            promotion_gate_runs.insert().values(**record.model_dump())
        )

    async def get_by_idempotency_key(
        self, connection: AsyncConnection, tenant_id: UUID, idempotency_key: str
    ) -> PromotionGateRun | None:
        result = await connection.execute(
            select(promotion_gate_runs).where(
                promotion_gate_runs.c.tenant_id == tenant_id,
                promotion_gate_runs.c.idempotency_key == idempotency_key,
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return PromotionGateRun.model_validate(dict(row))

    async def update_run(
        self,
        connection: AsyncConnection,
        run_id: UUID,
        *,
        fields: dict[str, object],
    ) -> int:
        result = await connection.execute(
            promotion_gate_runs.update()
            .where(promotion_gate_runs.c.run_id == run_id)
            .values(**fields)
        )
        return int(result.rowcount)
