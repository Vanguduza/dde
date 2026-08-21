"""Async repositories for `acceptance_oracles`, `verification_runs` and
`evidence` (Chapter 3.3, 3.8) -- all owned by `engine.verification`.

Every read and write here executes on the connection of an already-open
unit of work (Chapter 3.5); this module never begins or ends a transaction
itself.

`Pydantic.model_dump()` (default "python" mode) is required for the plain
`Uuid`/`TIMESTAMP` columns -- asyncpg's DBAPI layer wants real `uuid.UUID`/
`datetime` instances, not ISO strings (`mode="json"` breaks those columns).
But the same "python" mode leaves `UUID`/`datetime` values nested *inside*
the JSONB list/dict columns (e.g. `observable_outcomes`, `evidence_refs`) as
non-JSON-serialisable objects. `_json_safe` re-serialises only those
container values to plain JSON primitives before binding, so every column
gets the representation its own driver-level type actually needs.
"""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.acceptance_oracle import AcceptanceOracle
from engine.contracts.evidence import Evidence
from engine.contracts.verification_run import VerificationRun
from engine.verification.tables import acceptance_oracles, evidence, verification_runs

_ORACLE_JSONB_FIELDS = (
    "requirement_refs",
    "feature_refs",
    "observable_outcomes",
    "domain_invariants",
    "negative_cases",
    "human_assertions",
)
_RUN_JSONB_FIELDS = (
    "check_results",
    "outcome_results",
    "negative_case_results",
    "evidence_refs",
)
_EVIDENCE_JSONB_FIELDS = ("artifact_refs", "independence_flags")


def _json_safe(value: object) -> object:
    if isinstance(value, (list, dict)):
        return json.loads(json.dumps(value, default=str))
    return value


def _values(
    record: AcceptanceOracle | VerificationRun | Evidence, jsonb_fields: tuple[str, ...]
) -> dict[str, object]:
    dumped = record.model_dump()
    for field in jsonb_fields:
        dumped[field] = _json_safe(dumped[field])
    return dumped


class AcceptanceOracleRepository:
    """Reads and writes rows for `acceptance_oracles`."""

    async def insert_oracle(
        self, connection: AsyncConnection, record: AcceptanceOracle
    ) -> None:
        await connection.execute(
            acceptance_oracles.insert().values(**_values(record, _ORACLE_JSONB_FIELDS))
        )

    async def get_oracle(
        self, connection: AsyncConnection, oracle_id: UUID
    ) -> AcceptanceOracle | None:
        result = await connection.execute(
            select(acceptance_oracles).where(
                acceptance_oracles.c.oracle_id == oracle_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return AcceptanceOracle.model_validate(dict(row))

    async def get_by_version(
        self, connection: AsyncConnection, task_id: UUID, oracle_version: str
    ) -> AcceptanceOracle | None:
        """Definitions are immutable and content-hashed (Chapter 3.10): a
        second `define()` call for the same task with the same definition
        fields must find the existing row rather than mint a duplicate."""
        result = await connection.execute(
            select(acceptance_oracles).where(
                acceptance_oracles.c.task_id == task_id,
                acceptance_oracles.c.oracle_version == oracle_version,
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return AcceptanceOracle.model_validate(dict(row))


class VerificationRunRepository:
    """Reads and writes rows for `verification_runs`."""

    async def insert_run(
        self, connection: AsyncConnection, record: VerificationRun
    ) -> None:
        await connection.execute(
            verification_runs.insert().values(**_values(record, _RUN_JSONB_FIELDS))
        )

    async def update_run(
        self,
        connection: AsyncConnection,
        verification_run_id: UUID,
        *,
        fields: dict[str, object],
    ) -> int:
        safe_fields = {name: _json_safe(value) for name, value in fields.items()}
        result = await connection.execute(
            verification_runs.update()
            .where(verification_runs.c.verification_run_id == verification_run_id)
            .values(**safe_fields)
        )
        return result.rowcount

    async def get_run(
        self, connection: AsyncConnection, verification_run_id: UUID
    ) -> VerificationRun | None:
        result = await connection.execute(
            select(verification_runs).where(
                verification_runs.c.verification_run_id == verification_run_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return VerificationRun.model_validate(dict(row))

    async def list_for_worker_run(
        self, connection: AsyncConnection, worker_run_id: UUID
    ) -> list[VerificationRun]:
        result = await connection.execute(
            select(verification_runs)
            .where(verification_runs.c.worker_run_id == worker_run_id)
            .order_by(verification_runs.c.sequence.asc())
        )
        return [
            VerificationRun.model_validate(dict(row)) for row in result.mappings().all()
        ]

    async def list_for_task(
        self, connection: AsyncConnection, task_id: UUID
    ) -> list[VerificationRun]:
        result = await connection.execute(
            select(verification_runs)
            .where(verification_runs.c.task_id == task_id)
            .order_by(verification_runs.c.created_at.asc())
        )
        return [
            VerificationRun.model_validate(dict(row)) for row in result.mappings().all()
        ]

    async def next_sequence(
        self, connection: AsyncConnection, worker_run_id: UUID
    ) -> int:
        result = await connection.execute(
            select(func.coalesce(func.max(verification_runs.c.sequence), 0)).where(
                verification_runs.c.worker_run_id == worker_run_id
            )
        )
        return int(result.scalar_one()) + 1


class EvidenceRepository:
    """Reads and writes rows for `evidence` (Chapter 11.7: append-only)."""

    async def insert_evidence(
        self, connection: AsyncConnection, record: Evidence
    ) -> None:
        await connection.execute(
            evidence.insert().values(**_values(record, _EVIDENCE_JSONB_FIELDS))
        )

    async def get_evidence(
        self, connection: AsyncConnection, evidence_id: UUID
    ) -> Evidence | None:
        result = await connection.execute(
            select(evidence).where(evidence.c.evidence_id == evidence_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return Evidence.model_validate(dict(row))

    async def list_for_run(
        self, connection: AsyncConnection, verification_run_id: UUID
    ) -> list[Evidence]:
        result = await connection.execute(
            select(evidence)
            .where(evidence.c.verification_run_id == verification_run_id)
            .order_by(evidence.c.recorded_at.asc())
        )
        return [Evidence.model_validate(dict(row)) for row in result.mappings().all()]
