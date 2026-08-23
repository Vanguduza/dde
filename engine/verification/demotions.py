"""Durable record of guardrail-demoted PARTIAL VerificationRuns (EDR-0009,
accepted 2026-08-23).

Chapter 6.5's `routing_decision_outcomes` row is intentionally untouched:
`actual_verified_outcome` admits only PASSED/FAILED and
`RoutingTelemetryService.record_decision_outcome` gates on terminal status,
so a guardrail-demoted PARTIAL run produces no telemetry outcome. The
demotion itself is real product truth -- the population a learning pipeline
must never train on as successes and worth counting when tuning guardrail
thresholds -- so it is written HERE, by the same guarded runner path that
forces PARTIAL, keyed by `verification_run_id` for explicit joins.

`source` mirrors the recovery classification of the demotion:
`guardrail_test_scope_violation` (SCOPE_VIOLATION) or
`prototype_manifest_violation` (VERIFICATION_FAILURE) -- the same strings
the runner's `VerificationFailureRecovery` event carries, so a consumer can
reconcile the two without a second vocabulary.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.truth.db import PostgresUnitOfWork

DEMOTION_EVENT_TYPE: Final = "VerificationRunDemoted"

_SOURCE_GUARDRAIL: Final = "guardrail_test_scope_violation"
_SOURCE_PROTOTYPE: Final = "prototype_manifest_violation"

_INSERT = """
INSERT INTO verification_run_demotions (
    demotion_id, tenant_id, project_id, mission_id, task_id,
    worker_run_id, verification_run_id, source, failure_class,
    confidence, created_at
) VALUES (
    :demotion_id, :tenant_id, :project_id, :mission_id, :task_id,
    :worker_run_id, :verification_run_id, :source, :failure_class,
    :confidence, :created_at
)
ON CONFLICT (verification_run_id) DO NOTHING
"""


def source_for(violations: object) -> str:
    """The demotion source string for a guardrail vs prototype demotion --
    the same discriminator the runner's recovery event payload uses. Takes
    the violation collection itself (truthiness decides) so call sites read
    exactly like the recovery-event source branch."""
    return _SOURCE_GUARDRAIL if violations else _SOURCE_PROTOTYPE


class VerificationRunDemotionService:
    """Sole writer of `verification_run_demotions`. Called from the
    runner's PARTIAL-demoted branch inside the run's own transaction, so
    the demotion row commits or nothing does."""

    def __init__(self, engine: AsyncEngine, events: EventService | None = None) -> None:
        self._engine = engine
        self._events = events or EventService(engine)

    async def record(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        task_id: UUID,
        worker_run_id: UUID,
        verification_run_id: UUID,
        source: str,
        failure_class: str,
        confidence: float,
        uow: PostgresUnitOfWork,
    ) -> UUID:
        """Insert one demotion row (idempotent per verification run) plus
        its `VerificationRunDemoted` event, in the caller's unit of work.
        Returns the demotion row's id."""
        demotion_id = uuid7()
        await uow.connection.execute(
            text(_INSERT),
            {
                "demotion_id": demotion_id,
                "tenant_id": tenant_id,
                "project_id": project_id,
                "mission_id": mission_id,
                "task_id": task_id,
                "worker_run_id": worker_run_id,
                "verification_run_id": verification_run_id,
                "source": source,
                "failure_class": failure_class,
                "confidence": confidence,
                "created_at": datetime.now(UTC),
            },
        )
        await self._events.append(
            tenant_id=tenant_id,
            project_id=project_id,
            event_type=DEMOTION_EVENT_TYPE,
            aggregate_type="verification_run",
            aggregate_id=verification_run_id,
            mission_id=mission_id,
            task_id=task_id,
            payload={
                "demotion_id": str(demotion_id),
                "worker_run_id": str(worker_run_id),
                "source": source,
                "failure_class": failure_class,
                "confidence": confidence,
            },
            uow=uow,
        )
        return demotion_id
