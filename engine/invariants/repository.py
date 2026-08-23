"""Async repository for the Chapter 11.5 tables (Chapter 3.3, 3.8).

Every read and write executes on the connection of an already-open
`PostgresUnitOfWork`; this module never begins or ends a transaction.
JSONB container values are JSON-safe re-serialised before binding, the
same shape `engine.verification.repository` uses for its JSONB columns.
"""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.domain_invariant import DomainInvariant
from engine.contracts.invariant_evaluation import InvariantEvaluation
from engine.invariants.tables import domain_invariants, invariant_evaluations

_INVARIANT_JSONB_FIELDS = ("predicate",)
_EVALUATION_JSONB_FIELDS = ("violations",)


def _json_safe(value: object) -> object:
    if isinstance(value, (list, dict)):
        return json.loads(json.dumps(value, default=str))
    return value


def _values(
    record: DomainInvariant | InvariantEvaluation, jsonb_fields: tuple[str, ...]
) -> dict[str, object]:
    dumped = record.model_dump()
    for field in jsonb_fields:
        dumped[field] = _json_safe(dumped[field])
    return dumped


class InvariantRepository:
    """Reads and writes rows for `domain_invariants` and
    `invariant_evaluations`."""

    async def insert_invariant(
        self, connection: AsyncConnection, record: DomainInvariant
    ) -> None:
        values = _values(record, _INVARIANT_JSONB_FIELDS)
        await connection.execute(domain_invariants.insert().values(**values))

    async def get_invariant(
        self, connection: AsyncConnection, invariant_id: UUID
    ) -> DomainInvariant | None:
        result = await connection.execute(
            select(domain_invariants).where(
                domain_invariants.c.invariant_id == invariant_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return DomainInvariant.model_validate(dict(row))

    async def get_by_version(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        name: str,
        definition_version: str,
    ) -> DomainInvariant | None:
        """Definitions are immutable and content-hashed (Chapter 3.10): a
        second `define()` with identical definition fields must find the
        existing row rather than mint a duplicate."""
        result = await connection.execute(
            select(domain_invariants).where(
                domain_invariants.c.project_id == project_id,
                domain_invariants.c.name == name,
                domain_invariants.c.definition_version == definition_version,
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return DomainInvariant.model_validate(dict(row))

    async def list_active_for_project(
        self, connection: AsyncConnection, project_id: UUID
    ) -> list[DomainInvariant]:
        result = await connection.execute(
            select(domain_invariants).where(
                domain_invariants.c.project_id == project_id,
                domain_invariants.c.status == "ACTIVE",
            )
        )
        return [
            DomainInvariant.model_validate(dict(row)) for row in result.mappings().all()
        ]

    async def update_status(
        self,
        connection: AsyncConnection,
        invariant_id: UUID,
        *,
        status: str,
        updated_at: object,
    ) -> None:
        await connection.execute(
            domain_invariants.update()
            .where(domain_invariants.c.invariant_id == invariant_id)
            .values(status=status, updated_at=updated_at)
        )

    # --- evaluations --------------------------------------------------------

    async def insert_evaluation(
        self, connection: AsyncConnection, record: InvariantEvaluation
    ) -> None:
        await connection.execute(
            invariant_evaluations.insert().values(
                **_values(record, _EVALUATION_JSONB_FIELDS)
            )
        )

    async def get_evaluation(
        self, connection: AsyncConnection, evaluation_id: UUID
    ) -> InvariantEvaluation | None:
        result = await connection.execute(
            select(invariant_evaluations).where(
                invariant_evaluations.c.evaluation_id == evaluation_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return InvariantEvaluation.model_validate(dict(row))

    async def list_for_environment(
        self,
        connection: AsyncConnection,
        product_env_id: UUID,
        *,
        invariant_id: UUID | None = None,
    ) -> list[InvariantEvaluation]:
        conditions = [invariant_evaluations.c.product_env_id == product_env_id]
        if invariant_id is not None:
            conditions.append(invariant_evaluations.c.invariant_id == invariant_id)
        result = await connection.execute(
            select(invariant_evaluations)
            .where(*conditions)
            .order_by(invariant_evaluations.c.sequence.asc())
        )
        return [
            InvariantEvaluation.model_validate(dict(row))
            for row in result.mappings().all()
        ]

    async def next_sequence(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        project_id: UUID,
        invariant_id: UUID,
        product_env_id: UUID,
    ) -> int:
        result = await connection.execute(
            select(func.coalesce(func.max(invariant_evaluations.c.sequence), 0)).where(
                invariant_evaluations.c.tenant_id == tenant_id,
                invariant_evaluations.c.project_id == project_id,
                invariant_evaluations.c.invariant_id == invariant_id,
                invariant_evaluations.c.product_env_id == product_env_id,
            )
        )
        return int(result.scalar_one()) + 1
