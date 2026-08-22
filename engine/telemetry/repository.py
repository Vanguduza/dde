"""Async repository for `routing_decision_outcomes` (Chapter 3.3, 3.8).

Every read and write here executes on the connection of an already-open
unit of work (Chapter 3.5); this module never begins or ends a
transaction itself.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.routing_decision_outcome import RoutingDecisionOutcome
from engine.telemetry.tables import routing_decision_outcomes


class RoutingDecisionOutcomeRepository:
    """Reads and writes `routing_decision_outcomes` -- the Chapter 6.5
    durable record, owned by `engine.telemetry`."""

    async def insert_or_get(
        self, connection: AsyncConnection, record: RoutingDecisionOutcome
    ) -> tuple[RoutingDecisionOutcome, bool]:
        """Idempotent on `verification_run_id` (one telemetry outcome per
        verification run) via a single atomic `INSERT ... ON CONFLICT DO
        NOTHING RETURNING` -- the same race-safe pattern
        `engine.attribution.repository.FailureAttributionRepository`
        uses. Returns `(record, True)` when this call's row won,
        `(existing, False)` when a concurrent or prior call's row did."""
        result = await connection.execute(
            pg_insert(routing_decision_outcomes)
            .values(**record.model_dump())
            .on_conflict_do_nothing(index_elements=["verification_run_id"])
            .returning(routing_decision_outcomes)
        )
        row = result.mappings().first()
        if row is not None:
            return RoutingDecisionOutcome.model_validate(dict(row)), True
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
    ) -> RoutingDecisionOutcome | None:
        result = await connection.execute(
            select(routing_decision_outcomes).where(
                routing_decision_outcomes.c.verification_run_id == verification_run_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return RoutingDecisionOutcome.model_validate(dict(row))

    async def list_for_route_decision(
        self, connection: AsyncConnection, route_decision_id: UUID
    ) -> list[RoutingDecisionOutcome]:
        result = await connection.execute(
            select(routing_decision_outcomes)
            .where(routing_decision_outcomes.c.route_decision_id == route_decision_id)
            .order_by(routing_decision_outcomes.c.created_at.asc())
        )
        return [
            RoutingDecisionOutcome.model_validate(dict(row))
            for row in result.mappings().all()
        ]
