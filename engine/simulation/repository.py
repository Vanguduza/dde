"""Async repository for `routing_simulation_runs` (Chapter 3.3, 3.8).

Every read and write here executes on the connection of an already-open
unit of work (Chapter 3.5); this module never begins or ends a
transaction itself.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.routing_simulation_run import RoutingSimulationRun
from engine.simulation.tables import routing_simulation_runs


class RoutingSimulationRunRepository:
    """Reads and writes `routing_simulation_runs` -- the Chapter 6.4
    fixture-generator record, owned by `engine.simulation`."""

    async def insert_run(
        self, connection: AsyncConnection, record: RoutingSimulationRun
    ) -> None:
        await connection.execute(
            routing_simulation_runs.insert().values(**record.model_dump())
        )

    async def get_run(
        self, connection: AsyncConnection, run_id: UUID
    ) -> RoutingSimulationRun | None:
        result = await connection.execute(
            select(routing_simulation_runs).where(
                routing_simulation_runs.c.run_id == run_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return RoutingSimulationRun.model_validate(dict(row))

    async def list_for_project(
        self, connection: AsyncConnection, project_id: UUID
    ) -> list[RoutingSimulationRun]:
        result = await connection.execute(
            select(routing_simulation_runs)
            .where(routing_simulation_runs.c.project_id == project_id)
            .order_by(routing_simulation_runs.c.created_at.asc())
        )
        return [
            RoutingSimulationRun.model_validate(dict(row))
            for row in result.mappings().all()
        ]
