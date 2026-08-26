"""Async repository for Chapter 6.9 frozen policies and routing.mode.

Every read and write executes on an already-open unit of work (Chapter
3.5). This module never begins or ends a transaction itself. It does
not import `engine.routing.service` -- RouterService may import this
reader without a cycle.
"""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.learned_routing_policy import LearnedRoutingPolicy
from engine.contracts.routing_activation_state import RoutingActivationState
from engine.learning.tables import learned_routing_policies, routing_activation_state

_POLICY_JSONB = ("mapping", "training_experience_ids")


def _json_safe(value: object) -> object:
    if isinstance(value, (list, dict)):
        return json.loads(json.dumps(value, default=str))
    return value


def _policy_values(record: LearnedRoutingPolicy) -> dict[str, object]:
    dumped = record.model_dump()
    for field in _POLICY_JSONB:
        dumped[field] = _json_safe(dumped[field])
    return dumped


def _state_values(record: RoutingActivationState) -> dict[str, object]:
    return record.model_dump()


class LearningPolicyRepository:
    """Reads and writes frozen-policy artifacts and activation state."""

    async def insert_policy(
        self, connection: AsyncConnection, record: LearnedRoutingPolicy
    ) -> tuple[LearnedRoutingPolicy, bool]:
        """Idempotent on (tenant_id, project_id, policy_hash)."""
        result = await connection.execute(
            pg_insert(learned_routing_policies)
            .values(**_policy_values(record))
            .on_conflict_do_nothing(
                index_elements=["tenant_id", "project_id", "policy_hash"]
            )
            .returning(learned_routing_policies)
        )
        row = result.mappings().first()
        if row is not None:
            return LearnedRoutingPolicy.model_validate(dict(row)), True
        existing = await self.get_by_hash(
            connection,
            tenant_id=record.tenant_id,
            project_id=record.project_id,
            policy_hash=record.policy_hash,
        )
        if existing is None:  # pragma: no cover - defensive
            raise RuntimeError("insert_policy conflicted but no row could be read")
        return existing, False

    async def get(
        self, connection: AsyncConnection, policy_id: UUID
    ) -> LearnedRoutingPolicy | None:
        result = await connection.execute(
            select(learned_routing_policies).where(
                learned_routing_policies.c.policy_id == policy_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return LearnedRoutingPolicy.model_validate(dict(row))

    async def get_by_hash(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        project_id: UUID,
        policy_hash: str,
    ) -> LearnedRoutingPolicy | None:
        result = await connection.execute(
            select(learned_routing_policies).where(
                learned_routing_policies.c.tenant_id == tenant_id,
                learned_routing_policies.c.project_id == project_id,
                learned_routing_policies.c.policy_hash == policy_hash,
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return LearnedRoutingPolicy.model_validate(dict(row))

    async def get_latest(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        project_id: UUID,
    ) -> LearnedRoutingPolicy | None:
        result = await connection.execute(
            select(learned_routing_policies)
            .where(
                learned_routing_policies.c.tenant_id == tenant_id,
                learned_routing_policies.c.project_id == project_id,
            )
            .order_by(learned_routing_policies.c.created_at.desc())
            .limit(1)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return LearnedRoutingPolicy.model_validate(dict(row))

    async def update_status(
        self,
        connection: AsyncConnection,
        *,
        policy_id: UUID,
        status: str,
    ) -> LearnedRoutingPolicy | None:
        await connection.execute(
            update(learned_routing_policies)
            .where(learned_routing_policies.c.policy_id == policy_id)
            .values(status=status)
        )
        return await self.get(connection, policy_id)

    async def get_activation(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: UUID,
        project_id: UUID,
    ) -> RoutingActivationState | None:
        result = await connection.execute(
            select(routing_activation_state).where(
                routing_activation_state.c.tenant_id == tenant_id,
                routing_activation_state.c.project_id == project_id,
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return RoutingActivationState.model_validate(dict(row))

    async def upsert_activation(
        self, connection: AsyncConnection, record: RoutingActivationState
    ) -> RoutingActivationState:
        values = _state_values(record)
        update_cols = {
            key: values[key]
            for key in (
                "routing_mode",
                "active_policy_id",
                "last_certified_policy_id",
                "last_certified_mode",
                "canary_fraction",
                "continued_update_enabled",
                "updated_at",
            )
        }
        await connection.execute(
            pg_insert(routing_activation_state)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["tenant_id", "project_id"],
                set_=update_cols,
            )
        )
        loaded = await self.get_activation(
            connection, tenant_id=record.tenant_id, project_id=record.project_id
        )
        if loaded is None:  # pragma: no cover - defensive
            raise RuntimeError("upsert_activation wrote no row")
        return loaded
