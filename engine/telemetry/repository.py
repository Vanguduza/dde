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
from engine.routing.tables import route_decisions
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

    async def list_recent_with_selected_profiles(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        project_id: UUID,
        limit: int = 200,
    ) -> list[tuple[RoutingDecisionOutcome, str | None]]:
        """Recent outcomes joined to the selected profile id of the
        RouteDecision each outcome belongs to (Chapter 6.5's join back
        through ``route_decision_id``) -- the read pattern shadow promotion
        replays over, without duplicating it. Outcome rows carry no
        profile column; the RouteDecision is where selection was recorded.
        Returns oldest-first so windowed consumers can treat the list as
        an append-only stream.

        Scoped to ONE tenant and project. Health is a property of how a
        deployment's own profiles have been performing for that project;
        mixing in other tenants' outcomes (or unrelated suites sharing a
        dev database) lets foreign failure histories evict this caller's
        perfectly healthy profiles -- the same cross-tenant leak Chapter
        3.5/13.9 forbid everywhere else."""
        result = await connection.execute(
            select(
                routing_decision_outcomes,
                route_decisions.c.selected_worker_profile_id,
            )
            .join(
                route_decisions,
                routing_decision_outcomes.c.route_decision_id
                == route_decisions.c.decision_id,
            )
            .where(
                routing_decision_outcomes.c.tenant_id == tenant_id,
                routing_decision_outcomes.c.project_id == project_id,
            )
            .order_by(routing_decision_outcomes.c.created_at.desc())
            .limit(limit)
        )
        rows: list[tuple[RoutingDecisionOutcome, str | None]] = []
        for row in result.mappings().all():
            mapping = dict(row)
            mapping.pop("selected_worker_profile_id", None)
            rows.append(
                (
                    RoutingDecisionOutcome.model_validate(mapping),
                    row["selected_worker_profile_id"],
                )
            )
        rows.reverse()
        return rows

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
