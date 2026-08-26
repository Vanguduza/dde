"""Production Chapter 6.8 ExperienceRecord engine -- the sole writer of
`experience_records` rows in PostgreSQL (Chapter 2.6, 3.5, 3.8).

Two production mutation call sites:

1. `record_from_verification()` -- `engine.verification.runner.
   VerificationRunnerService.run()` calls it for every terminal (`PASSED`
   or `FAILED`) `VerificationRun`, inside the same transaction as that
   run's telemetry write. Chapter 6.8 eligibility is computed from the
   already-persisted `RouteDecision` + `RoutingDecisionOutcome` +
   optional `FailureAttribution` + active flaky quarantines, never from
   caller-supplied verdicts.
2. `record_from_simulation()` -- `engine.simulation.service.
   RoutingSimulationService.run_regression()` writes one simulation-origin
   row per completed simulation run. `eligible_for_routing_training` is
   forced false; a table CHECK refuses any other value (Chapter 6.4:
   excluded by construction).

`queue_for_learning()` is the governed promotion-state mutation
(Chapter 3.8: "Promotion state only"). It refuses ineligible,
superseded, blocked, consumed, or simulation-origin rows -- DDE-058's
learner cannot bypass Chapter 6.8 by attaching a new `learning_run_id`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.attribution.repository import FailureAttributionRepository
from engine.contracts.experience_record import ExperienceRecord
from engine.contracts.routing_simulation_run import RoutingSimulationRun
from engine.contracts.task import Task
from engine.contracts.verification_run import VerificationRun
from engine.contracts.worker_run import WorkerRun
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.hashing import canonical_json, sha256_hex
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.execution.repository import ExecutionPlanRepository
from engine.learning import rules
from engine.learning.repository import ExperienceRecordRepository
from engine.routing.repository import RouteDecisionRepository
from engine.telemetry.repository import RoutingDecisionOutcomeRepository
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work
from engine.verification.flaky_quarantine import FlakyQuarantineService

T = TypeVar("T")


class ExperienceRecordService:
    """Async, PostgreSQL-backed writer for `experience_records`
    (Chapter 3.8). Each public method opens and commits its own unit of
    work unless one is supplied, so a caller composing a cross-module
    transaction (Chapter 3.5) can share it instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        events: EventService | None = None,
        repository: ExperienceRecordRepository | None = None,
        telemetry: RoutingDecisionOutcomeRepository | None = None,
        routes: RouteDecisionRepository | None = None,
        execution_plans: ExecutionPlanRepository | None = None,
        attributions: FailureAttributionRepository | None = None,
        flaky_quarantine: FlakyQuarantineService | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._events = events or EventService(engine)
        self._repository = repository or ExperienceRecordRepository()
        self._telemetry = telemetry or RoutingDecisionOutcomeRepository()
        self._routes = routes or RouteDecisionRepository()
        self._execution_plans = execution_plans or ExecutionPlanRepository()
        self._attributions = attributions or FailureAttributionRepository()
        self._flaky_quarantine = flaky_quarantine or FlakyQuarantineService(
            engine, events=self._events
        )
        self._clock = clock or SystemClock()

    async def _run(
        self,
        uow: PostgresUnitOfWork | None,
        tenant_id: UUID,
        project_id: UUID,
        body: Callable[[PostgresUnitOfWork], Awaitable[T]],
    ) -> T:
        if uow is not None:
            return await body(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as owned:
            result = await body(owned)
            await owned.commit()
            return result

    async def record_from_verification(
        self,
        *,
        task: Task,
        worker_run: WorkerRun,
        verification_run: VerificationRun,
        failed_check_refs: Sequence[str] = (),
        uow: PostgresUnitOfWork | None = None,
    ) -> ExperienceRecord:
        """Chapter 6.8: persist the eligibility-filtered experience for a
        terminal real verification, joining the already-written telemetry
        and (on FAILED) attribution rows in the same transaction."""
        if verification_run.status not in ("PASSED", "FAILED"):
            raise DdeError(
                "POLICY_DENIED",
                "ExperienceRecord is recorded only for a terminal VerificationRun",
                details={"status": verification_run.status},
            )

        async def _op(active: PostgresUnitOfWork) -> ExperienceRecord:
            outcome = await self._telemetry.get_by_verification_run(
                active.connection, verification_run.verification_run_id
            )
            if outcome is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "ExperienceRecord requires the same-transaction "
                    "RoutingDecisionOutcome",
                    details={
                        "verification_run_id": str(verification_run.verification_run_id)
                    },
                )
            decision = await self._routes.get_route_decision(
                active.connection, outcome.route_decision_id
            )
            if decision is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "ExperienceRecord requires the RouteDecision behind the outcome",
                    details={"route_decision_id": str(outcome.route_decision_id)},
                )
            attribution = None
            if outcome.failure_attribution_id is not None:
                attribution = await self._attributions.get_by_verification_run(
                    active.connection, verification_run.verification_run_id
                )
            quarantined_refs = await self._flaky_quarantine.list_active(
                tenant_id=task.tenant_id,
                project_id=task.project_id,
                task_id=task.task_id,
                uow=active,
            )
            active_refs = {row.check_ref for row in quarantined_refs if row.active}
            flaky_quarantined = any(ref in active_refs for ref in failed_check_refs)

            mapped, attr_confidence = rules.map_failure_attribution(
                actual_verified_outcome=outcome.actual_verified_outcome,
                attribution_outcome=(
                    attribution.outcome if attribution is not None else None
                ),
                attribution_confidence=(
                    attribution.confidence if attribution is not None else None
                ),
            )
            verdict = rules.evaluate_eligibility(
                experience_origin="real",
                verification_confidence=float(outcome.verification_confidence),
                failure_attribution=mapped,
                attribution_confidence=float(attr_confidence),
                terminal=True,
                flaky_quarantined=flaky_quarantined,
            )
            now = self._clock.now()
            experience_id = uuid7()
            candidate = ExperienceRecord(
                experience_id=experience_id,
                tenant_id=task.tenant_id,
                project_id=task.project_id,
                mission_id=task.mission_id,
                task_id=task.task_id,
                route_decision_id=decision.decision_id,
                task_attempt_id=worker_run.task_attempt_id,
                verification_run_id=verification_run.verification_run_id,
                routing_simulation_run_id=None,
                outcome_id=outcome.outcome_id,
                experience_origin="real",
                routing_policy_version=decision.policy_version,
                candidate_set_hash=sha256_hex(canonical_json(decision.candidates)),
                selection_propensity=float(decision.selection_propensity),
                prediction_vector={
                    "predicted_success": decision.predicted_success,
                    "predicted_cost": decision.predicted_cost,
                    "predicted_latency": decision.predicted_latency,
                    "confidence": decision.confidence,
                },
                observed_outcome_vector={
                    "actual_verified_outcome": outcome.actual_verified_outcome,
                    "rework_count": outcome.rework_count,
                    "elapsed_seconds": outcome.elapsed_seconds,
                    "escalated": outcome.escalated,
                    "human_intervention_required": (
                        outcome.human_intervention_required
                    ),
                },
                verification_confidence=float(outcome.verification_confidence),
                failure_attribution=verdict.failure_attribution,
                attribution_confidence=verdict.attribution_confidence,
                holdout_partition=rules.holdout_partition(experience_id),
                promotion_evidence_refs=[],
                drift_snapshot_id=None,
                learning_run_id=None,
                eligible_for_routing_training=verdict.eligible_for_routing_training,
                eligibility_reasons=list(verdict.reasons),
                down_weighted=verdict.down_weighted,
                promotion_state="unpromoted",
                created_at=now,
                updated_at=now,
            )
            record, was_new = await self._repository.insert_or_get(
                active.connection, candidate
            )
            if was_new:
                await self._repository.supersede_prior_for_task(
                    active.connection,
                    task_id=task.task_id,
                    except_experience_id=record.experience_id,
                    now=now,
                )
                await self._events.append(
                    tenant_id=task.tenant_id,
                    project_id=task.project_id,
                    event_type="ExperienceRecordRecorded",
                    aggregate_type="experience_record",
                    aggregate_id=record.experience_id,
                    mission_id=task.mission_id,
                    task_id=task.task_id,
                    payload={
                        "verification_run_id": str(
                            verification_run.verification_run_id
                        ),
                        "experience_origin": record.experience_origin,
                        "eligible_for_routing_training": (
                            record.eligible_for_routing_training
                        ),
                        "failure_attribution": record.failure_attribution,
                    },
                    uow=active,
                )
            return record

        return await self._run(uow, task.tenant_id, task.project_id, _op)

    async def record_from_simulation(
        self,
        *,
        run: RoutingSimulationRun,
        uow: PostgresUnitOfWork | None = None,
    ) -> ExperienceRecord:
        """Chapter 6.4/6.8: persist a simulation-origin ExperienceRecord
        that is excluded from routing training by construction."""

        async def _op(active: PostgresUnitOfWork) -> ExperienceRecord:
            verdict = rules.evaluate_eligibility(
                experience_origin="simulation",
                verification_confidence=0.0,
                failure_attribution="none",
                attribution_confidence=0.0,
                terminal=True,
                flaky_quarantined=False,
            )
            now = self._clock.now()
            experience_id = uuid7()
            candidate = ExperienceRecord(
                experience_id=experience_id,
                tenant_id=run.tenant_id,
                project_id=run.project_id,
                mission_id=None,
                task_id=None,
                route_decision_id=None,
                task_attempt_id=None,
                verification_run_id=None,
                routing_simulation_run_id=run.run_id,
                outcome_id=None,
                experience_origin="simulation",
                routing_policy_version=run.policy_version,
                candidate_set_hash=sha256_hex(canonical_json(run.scenario_results)),
                selection_propensity=1.0,
                prediction_vector={},
                observed_outcome_vector={
                    "source": "simulation",
                    "scenario_count": len(run.scenario_results),
                    "model_version": run.model_version,
                    "seed": run.seed,
                },
                verification_confidence=0.0,
                failure_attribution=verdict.failure_attribution,
                attribution_confidence=verdict.attribution_confidence,
                holdout_partition=rules.holdout_partition(experience_id),
                promotion_evidence_refs=[],
                drift_snapshot_id=None,
                learning_run_id=None,
                eligible_for_routing_training=False,
                eligibility_reasons=list(verdict.reasons),
                down_weighted=verdict.down_weighted,
                promotion_state="unpromoted",
                created_at=now,
                updated_at=now,
            )
            record, was_new = await self._repository.insert_or_get(
                active.connection, candidate
            )
            if was_new:
                await self._events.append(
                    tenant_id=run.tenant_id,
                    project_id=run.project_id,
                    event_type="ExperienceRecordRecorded",
                    aggregate_type="experience_record",
                    aggregate_id=record.experience_id,
                    mission_id=None,
                    task_id=None,
                    payload={
                        "routing_simulation_run_id": str(run.run_id),
                        "experience_origin": "simulation",
                        "eligible_for_routing_training": False,
                    },
                    uow=active,
                )
            return record

        return await self._run(uow, run.tenant_id, run.project_id, _op)

    async def queue_for_learning(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        experience_id: UUID,
        learning_run_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> ExperienceRecord:
        """Governed promotion-state mutation. Refuses any row Chapter 6.8
        would exclude from a training population -- a new learning_run_id
        cannot bypass eligibility."""

        async def _op(active: PostgresUnitOfWork) -> ExperienceRecord:
            record = await self._repository.get(active.connection, experience_id)
            if record is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "Unknown ExperienceRecord",
                    details={"experience_id": str(experience_id)},
                )
            if record.experience_origin != "real":
                raise DdeError(
                    "POLICY_DENIED",
                    "simulation ExperienceRecords cannot enter a learning run",
                    details={"experience_id": str(experience_id)},
                )
            if not record.eligible_for_routing_training:
                raise DdeError(
                    "POLICY_DENIED",
                    "ineligible ExperienceRecord cannot be queued for learning",
                    details={
                        "experience_id": str(experience_id),
                        "eligibility_reasons": list(record.eligibility_reasons),
                    },
                )
            if record.promotion_state not in ("unpromoted", "queued_for_learning"):
                raise DdeError(
                    "POLICY_DENIED",
                    "ExperienceRecord promotion_state is not queueable",
                    details={
                        "experience_id": str(experience_id),
                        "promotion_state": record.promotion_state,
                    },
                )
            updated = await self._repository.update_promotion_state(
                active.connection,
                experience_id=experience_id,
                promotion_state="queued_for_learning",
                now=self._clock.now(),
                learning_run_id=learning_run_id,
            )
            if updated is None:  # pragma: no cover - defensive
                raise DdeError(
                    "POLICY_DENIED",
                    "ExperienceRecord vanished during promotion-state update",
                    details={"experience_id": str(experience_id)},
                )
            return updated

        return await self._run(uow, tenant_id, project_id, _op)

    async def list_eligible_for_training(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[ExperienceRecord]:
        async def _op(active: PostgresUnitOfWork) -> list[ExperienceRecord]:
            return await self._repository.list_eligible_for_training(
                active.connection, tenant_id=tenant_id, project_id=project_id
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def get_for_verification_run(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        verification_run_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> ExperienceRecord | None:
        async def _op(active: PostgresUnitOfWork) -> ExperienceRecord | None:
            return await self._repository.get_by_verification_run(
                active.connection, verification_run_id
            )

        return await self._run(uow, tenant_id, project_id, _op)
