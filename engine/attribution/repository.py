"""Async repository for `failure_attributions` (Chapter 3.3, 3.8).

Every read and write here executes on the connection of an already-open
unit of work (Chapter 3.5); this module never begins or ends a
transaction itself.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.attribution.tables import failure_attributions
from engine.contracts.failure_attribution import FailureAttribution


class FailureAttributionRepository:
    """Reads and writes `failure_attributions` -- the Chapter 5.11
    durable record, owned by `engine.attribution`."""

    async def insert_or_get(
        self, connection: AsyncConnection, record: FailureAttribution
    ) -> tuple[FailureAttribution, bool]:
        """Idempotent on `verification_run_id` (one attribution per
        verification run) via a single atomic `INSERT ... ON CONFLICT DO
        NOTHING RETURNING` -- unlike a separate check-then-insert, this
        cannot race: two concurrent callers attributing the same
        `VerificationRun` can never both observe "no existing row" and
        both insert. Returns `(record, True)` when this call's row won,
        `(existing, False)` when a concurrent or prior call's row did."""
        result = await connection.execute(
            pg_insert(failure_attributions)
            .values(**record.model_dump())
            .on_conflict_do_nothing(index_elements=["verification_run_id"])
            .returning(failure_attributions)
        )
        row = result.mappings().first()
        if row is not None:
            return FailureAttribution.model_validate(dict(row)), True
        existing = await self.get_by_verification_run(
            connection, record.verification_run_id
        )
        if existing is None:  # pragma: no cover - defensive, see docstring
            raise RuntimeError(
                "insert_or_get conflicted but no existing row could be read back"
            )
        return existing, False

    async def get_by_verification_run(
        self, connection: AsyncConnection, verification_run_id: UUID
    ) -> FailureAttribution | None:
        result = await connection.execute(
            select(failure_attributions).where(
                failure_attributions.c.verification_run_id == verification_run_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return FailureAttribution.model_validate(dict(row))

    async def list_for_task(
        self, connection: AsyncConnection, task_id: UUID
    ) -> list[FailureAttribution]:
        result = await connection.execute(
            select(failure_attributions)
            .where(failure_attributions.c.task_id == task_id)
            .order_by(failure_attributions.c.created_at.asc())
        )
        return [
            FailureAttribution.model_validate(dict(row))
            for row in result.mappings().all()
        ]
