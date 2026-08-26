"""Async repository for `experience_records` (Chapter 3.3, 3.8).

Every read and write here executes on the connection of an already-open
unit of work (Chapter 3.5); this module never begins or ends a
transaction itself.

Inserts are idempotent on the origin-appropriate unique key
(`verification_run_id` for real rows, `routing_simulation_run_id` for
simulation) via atomic `INSERT ... ON CONFLICT DO NOTHING RETURNING`.
After insert, the only permitted mutation is promotion state (Chapter
3.8) -- observational fields are never rewritten.
"""

from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.experience_record import ExperienceRecord
from engine.learning.tables import experience_records

_JSONB_FIELDS = (
    "prediction_vector",
    "observed_outcome_vector",
    "promotion_evidence_refs",
    "eligibility_reasons",
)

_PROMOTION_MUTABLE = frozenset(
    {
        "promotion_state",
        "promotion_evidence_refs",
        "learning_run_id",
        "drift_snapshot_id",
        "updated_at",
    }
)


def _json_safe(value: object) -> object:
    if isinstance(value, (list, dict)):
        return json.loads(json.dumps(value, default=str))
    return value


def _values(record: ExperienceRecord) -> dict[str, object]:
    dumped = record.model_dump()
    for field in _JSONB_FIELDS:
        dumped[field] = _json_safe(dumped[field])
    return dumped


class ExperienceRecordRepository:
    """Reads and writes `experience_records` -- the Chapter 6.8 durable
    record, owned by `engine.learning`."""

    async def insert_or_get(
        self, connection: AsyncConnection, record: ExperienceRecord
    ) -> tuple[ExperienceRecord, bool]:
        """Idempotent on the origin-appropriate unique column."""
        conflict = (
            "routing_simulation_run_id"
            if record.experience_origin == "simulation"
            else "verification_run_id"
        )
        result = await connection.execute(
            pg_insert(experience_records)
            .values(**_values(record))
            .on_conflict_do_nothing(index_elements=[conflict])
            .returning(experience_records)
        )
        row = result.mappings().first()
        if row is not None:
            return ExperienceRecord.model_validate(dict(row)), True
        if record.experience_origin == "simulation":
            sim_id = record.routing_simulation_run_id
            if sim_id is None:
                raise RuntimeError(
                    "simulation ExperienceRecord missing routing_simulation_run_id"
                )
            existing = await self.get_by_simulation_run(connection, sim_id)
        else:
            verification_id = record.verification_run_id
            if verification_id is None:
                raise RuntimeError("real ExperienceRecord missing verification_run_id")
            existing = await self.get_by_verification_run(connection, verification_id)
        if existing is None:  # pragma: no cover - defensive
            raise RuntimeError(
                "insert_or_get conflicted but no existing row could be read back"
            )
        return existing, False

    async def get_by_verification_run(
        self, connection: AsyncConnection, verification_run_id: UUID
    ) -> ExperienceRecord | None:
        result = await connection.execute(
            select(experience_records).where(
                experience_records.c.verification_run_id == verification_run_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return ExperienceRecord.model_validate(dict(row))

    async def get_by_simulation_run(
        self, connection: AsyncConnection, routing_simulation_run_id: UUID
    ) -> ExperienceRecord | None:
        result = await connection.execute(
            select(experience_records).where(
                experience_records.c.routing_simulation_run_id
                == routing_simulation_run_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return ExperienceRecord.model_validate(dict(row))

    async def get(
        self, connection: AsyncConnection, experience_id: UUID
    ) -> ExperienceRecord | None:
        result = await connection.execute(
            select(experience_records).where(
                experience_records.c.experience_id == experience_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return ExperienceRecord.model_validate(dict(row))

    async def list_eligible_for_training(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        project_id: UUID,
    ) -> list[ExperienceRecord]:
        """Chapter 6.8 production read: only real, still-unconsumed,
        write-time-eligible rows. Simulation cannot appear here even if a
        caller forgets the origin filter -- `eligible_for_routing_training`
        is forced false by both the writer and a table CHECK."""
        result = await connection.execute(
            select(experience_records)
            .where(
                experience_records.c.tenant_id == tenant_id,
                experience_records.c.project_id == project_id,
                experience_records.c.experience_origin == "real",
                experience_records.c.eligible_for_routing_training.is_(True),
                experience_records.c.promotion_state.in_(
                    ("unpromoted", "queued_for_learning")
                ),
            )
            .order_by(experience_records.c.created_at.asc())
        )
        return [
            ExperienceRecord.model_validate(dict(row))
            for row in result.mappings().all()
        ]

    async def list_for_task(
        self, connection: AsyncConnection, task_id: UUID
    ) -> list[ExperienceRecord]:
        result = await connection.execute(
            select(experience_records)
            .where(experience_records.c.task_id == task_id)
            .order_by(experience_records.c.created_at.asc())
        )
        return [
            ExperienceRecord.model_validate(dict(row))
            for row in result.mappings().all()
        ]

    async def supersede_prior_for_task(
        self,
        connection: AsyncConnection,
        *,
        task_id: UUID,
        except_experience_id: UUID,
        now: datetime,
    ) -> int:
        """Chapter 6.8 condition 4: a later terminal attempt supersedes
        earlier ones. Consumed rows stay consumed (already attached to a
        learning run); superseded/blocked are left alone."""
        result = await connection.execute(
            update(experience_records)
            .where(
                experience_records.c.task_id == task_id,
                experience_records.c.experience_id != except_experience_id,
                experience_records.c.promotion_state.in_(
                    ("unpromoted", "queued_for_learning")
                ),
            )
            .values(promotion_state="superseded", updated_at=now)
        )
        return int(result.rowcount or 0)

    async def update_promotion_state(
        self,
        connection: AsyncConnection,
        *,
        experience_id: UUID,
        promotion_state: str,
        now: datetime,
        promotion_evidence_refs: list[UUID] | None = None,
        learning_run_id: UUID | None = None,
        drift_snapshot_id: UUID | None = None,
    ) -> ExperienceRecord | None:
        """Chapter 3.8: the only mutation after creation. Keys outside
        `_PROMOTION_MUTABLE` are structurally unreachable from this
        method's values dict."""
        values: dict[str, object] = {
            "promotion_state": promotion_state,
            "updated_at": now,
        }
        if promotion_evidence_refs is not None:
            values["promotion_evidence_refs"] = _json_safe(
                [str(item) for item in promotion_evidence_refs]
            )
        if learning_run_id is not None:
            values["learning_run_id"] = learning_run_id
        if drift_snapshot_id is not None:
            values["drift_snapshot_id"] = drift_snapshot_id
        extra = set(values) - _PROMOTION_MUTABLE
        if extra:
            raise RuntimeError(
                f"update_promotion_state refused non-promotion fields: {sorted(extra)}"
            )
        await connection.execute(
            update(experience_records)
            .where(experience_records.c.experience_id == experience_id)
            .values(**values)
        )
        return await self.get(connection, experience_id)
