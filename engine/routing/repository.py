"""Async repository for `route_decisions` (Chapter 3.3, 3.8).

Every read and write here executes on the connection of an already-open
unit of work (Chapter 3.5); this module never begins or ends a transaction
itself.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.route_decision import RouteDecision
from engine.routing.tables import route_decisions


class RouteDecisionRepository:
    """Reads and writes rows for `route_decisions` — the Chapter 3.8 table
    owned by `engine.routing`."""

    async def insert_route_decision(
        self, connection: AsyncConnection, record: RouteDecision
    ) -> None:
        await connection.execute(route_decisions.insert().values(**record.model_dump()))

    async def get_route_decision(
        self, connection: AsyncConnection, decision_id: UUID
    ) -> RouteDecision | None:
        result = await connection.execute(
            select(route_decisions).where(route_decisions.c.decision_id == decision_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return RouteDecision.model_validate(dict(row))

    async def list_for_task(
        self, connection: AsyncConnection, task_id: UUID
    ) -> list[RouteDecision]:
        result = await connection.execute(
            select(route_decisions)
            .where(route_decisions.c.task_id == task_id)
            .order_by(route_decisions.c.created_at.asc())
        )
        return [
            RouteDecision.model_validate(dict(row)) for row in result.mappings().all()
        ]

    async def list_for_project(
        self, connection: AsyncConnection, project_id: UUID, *, limit: int = 50
    ) -> list[RouteDecision]:
        result = await connection.execute(
            select(route_decisions)
            .where(route_decisions.c.project_id == project_id)
            .order_by(route_decisions.c.created_at.desc())
            .limit(limit)
        )
        return [
            RouteDecision.model_validate(dict(row)) for row in result.mappings().all()
        ]

    async def list_for_mission(
        self, connection: AsyncConnection, mission_id: UUID
    ) -> list[RouteDecision]:
        result = await connection.execute(
            select(route_decisions)
            .where(route_decisions.c.mission_id == mission_id)
            .order_by(route_decisions.c.created_at.asc())
        )
        return [
            RouteDecision.model_validate(dict(row)) for row in result.mappings().all()
        ]
