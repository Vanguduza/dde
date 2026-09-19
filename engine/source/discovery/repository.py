"""Scoped persistence for EDR-0019 discovery."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.discovery_candidate import DiscoveryCandidate
from engine.contracts.discovery_observation import DiscoveryObservation
from engine.contracts.discovery_qualification import DiscoveryQualification
from engine.contracts.discovery_transition import DiscoveryTransition
from engine.contracts.discovery_trial import DiscoveryTrial
from engine.contracts.graph_trust_projection import GraphTrustProjection
from engine.source.discovery.tables import (
    discovery_candidates,
    discovery_observations,
    discovery_qualifications,
    discovery_transitions,
    discovery_trials,
    graph_trust_projections,
)


def _payload(model: object) -> dict[str, object]:
    data = model.model_dump(mode="python")  # type: ignore[attr-defined]
    for key, value in tuple(data.items()):
        if isinstance(value, tuple):
            data[key] = list(value)
    return cast(dict[str, object], data)


class DiscoveryRepository:
    async def get_candidate(
        self, connection: AsyncConnection, *, candidate_id: UUID
    ) -> DiscoveryCandidate | None:
        row = (
            (
                await connection.execute(
                    select(discovery_candidates).where(
                        discovery_candidates.c.candidate_id == candidate_id
                    )
                )
            )
            .mappings()
            .first()
        )
        return DiscoveryCandidate.model_validate(dict(row)) if row else None

    async def insert_candidate(
        self, connection: AsyncConnection, *, candidate: DiscoveryCandidate
    ) -> None:
        await connection.execute(insert(discovery_candidates), _payload(candidate))

    async def update_candidate(
        self, connection: AsyncConnection, *, candidate: DiscoveryCandidate
    ) -> None:
        payload = _payload(candidate)
        payload.pop("candidate_id")
        await connection.execute(
            update(discovery_candidates)
            .where(discovery_candidates.c.candidate_id == candidate.candidate_id)
            .values(**payload)
        )

    async def next_sequence(
        self, connection: AsyncConnection, *, candidate_id: UUID
    ) -> int:
        current = (
            await connection.execute(
                select(func.max(discovery_transitions.c.sequence)).where(
                    discovery_transitions.c.candidate_id == candidate_id
                )
            )
        ).scalar()
        return int(current or 0) + 1

    async def append_transition(
        self, connection: AsyncConnection, *, transition: DiscoveryTransition
    ) -> None:
        await connection.execute(insert(discovery_transitions), _payload(transition))

    async def list_transitions(
        self, connection: AsyncConnection, *, candidate_id: UUID
    ) -> list[DiscoveryTransition]:
        rows = (
            (
                await connection.execute(
                    select(discovery_transitions)
                    .where(discovery_transitions.c.candidate_id == candidate_id)
                    .order_by(discovery_transitions.c.sequence)
                )
            )
            .mappings()
            .all()
        )
        return [DiscoveryTransition.model_validate(dict(row)) for row in rows]

    async def insert_observation(
        self, connection: AsyncConnection, *, observation: DiscoveryObservation
    ) -> None:
        await connection.execute(insert(discovery_observations), _payload(observation))

    async def insert_trial(
        self, connection: AsyncConnection, *, trial: DiscoveryTrial
    ) -> None:
        await connection.execute(insert(discovery_trials), _payload(trial))

    async def update_trial(
        self, connection: AsyncConnection, *, trial: DiscoveryTrial
    ) -> None:
        payload = _payload(trial)
        payload.pop("trial_id")
        await connection.execute(
            update(discovery_trials)
            .where(discovery_trials.c.trial_id == trial.trial_id)
            .values(**payload)
        )

    async def insert_qualification(
        self, connection: AsyncConnection, *, qualification: DiscoveryQualification
    ) -> None:
        await connection.execute(
            insert(discovery_qualifications), _payload(qualification)
        )

    async def insert_projection(
        self, connection: AsyncConnection, *, projection: GraphTrustProjection
    ) -> None:
        await connection.execute(insert(graph_trust_projections), _payload(projection))
