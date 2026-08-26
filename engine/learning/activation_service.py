"""Production Chapter 6.9 learning-activation mutations (DDE-058).

Call sites:

- `fit_frozen_policy()` -- TRAIN + OFFLINE EVALUATE. The sole writer of
  `learned_routing_policies`. Refuses a cold-start (empty train
  partition). Always writes `continued_update=false` (frozen-first).
- `attempt_advance()` -- the sole writer that may request a forward
  `routing.mode` change. Reads the durable current mode (a caller cannot
  skip by supplying a later `current_mode`), evaluates Chapter 6.9
  gates, and upserts `routing_activation_state` only when allowed.
- `rollback()` -- reachable from any mode; returns to the last certified
  policy (the declared deterministic table when none is certified) and
  never to an untested fallback. The frozen artifact is left in place.
- `attempt_online_update()` -- the partial-information path. Always
  refused until an explicit continued-update switch exists *and* that
  switch has its own canary evidence. This mission does not implement
  the updater; refusal is the control.

`RouterService.route()` is the production reader of activation state
(canary / promoted_historical / shadow annotation). Live
`engine.routing.policy` (the declared table) is never rewritten.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.learned_routing_policy import LearnedRoutingPolicy
from engine.contracts.routing_activation_state import RoutingActivationState
from engine.contracts.task import Task
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.learning.activation import (
    DEFAULT_CANARY_FRACTION,
    ActivationThresholds,
    ActivationVerdict,
    RoutingMode,
    evaluate_activation_gates,
    last_certified_mode,
)
from engine.learning.learner import FrozenFit, OutcomeObservation
from engine.learning.learner import (
    fit_frozen_policy as compute_frozen_fit,
)
from engine.learning.policy_repository import LearningPolicyRepository
from engine.learning.repository import ExperienceRecordRepository
from engine.routing.policy import HUMAN_DECISION_TASK
from engine.routing.repository import RouteDecisionRepository
from engine.routing.rules import evaluate
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")


def _now(clock: Clock) -> datetime:
    stamped = clock.now()
    if stamped.tzinfo is None:
        return stamped.replace(tzinfo=UTC)
    return stamped


class LearningActivationService:
    """Evaluates Chapter 6.9 gates and persists frozen fits / mode state."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: ExperienceRecordRepository | None = None,
        routes: RouteDecisionRepository | None = None,
        policies: LearningPolicyRepository | None = None,
        events: EventService | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or ExperienceRecordRepository()
        self._routes = routes or RouteDecisionRepository()
        self._policies = policies or LearningPolicyRepository()
        self._events = events or EventService(engine)
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

    async def fit_frozen_policy(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        learning_run_id: UUID | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> LearnedRoutingPolicy:
        """TRAIN + OFFLINE EVALUATE: persist a frozen full-information fit.

        Cold-start (no train-partition eligible records) is POLICY_DENIED.
        Simulation rows cannot appear in `list_eligible_for_training`.
        """

        async def _op(active: PostgresUnitOfWork) -> LearnedRoutingPolicy:
            records = await self._repository.list_eligible_for_training(
                active.connection, tenant_id=tenant_id, project_id=project_id
            )
            observations: list[OutcomeObservation] = []
            for row in records:
                if row.route_decision_id is None:
                    continue
                decision = await self._routes.get_route_decision(
                    active.connection, row.route_decision_id
                )
                if decision is None:
                    continue
                outcome = row.observed_outcome_vector.get("actual_verified_outcome")
                observations.append(
                    OutcomeObservation(
                        experience_id=row.experience_id,
                        workload_class=decision.workload_class,
                        selected_profile_id=decision.selected_worker_profile_id,
                        success=outcome == "PASSED",
                        holdout_partition=row.holdout_partition,
                        down_weighted=row.down_weighted,
                    )
                )
            fallback_ok = _fallback_robustness(observations)
            fit = compute_frozen_fit(
                observations,
                fallback_robustness_demonstrated=fallback_ok,
            )
            if fit.refused_reason is not None:
                raise DdeError(
                    "POLICY_DENIED",
                    "offline full-information fit refused",
                    details={"reason": fit.refused_reason},
                )
            now = _now(self._clock)
            run_id = learning_run_id or uuid7()
            candidate = _policy_from_fit(
                fit,
                tenant_id=tenant_id,
                project_id=project_id,
                learning_run_id=run_id,
                now=now,
            )
            stored, was_new = await self._policies.insert_policy(
                active.connection, candidate
            )
            if was_new:
                for experience_id in fit.training_experience_ids:
                    await self._repository.update_promotion_state(
                        active.connection,
                        experience_id=experience_id,
                        promotion_state="consumed",
                        now=now,
                        learning_run_id=stored.learning_run_id,
                    )
                await self._events.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    event_type="LearnedRoutingPolicyFitted",
                    aggregate_type="learned_routing_policy",
                    aggregate_id=stored.policy_id,
                    payload={
                        "policy_hash": stored.policy_hash,
                        "train_count": stored.train_count,
                        "holdout_count": stored.holdout_count,
                        "beats_constant_policy": stored.beats_constant_policy,
                    },
                    uow=active,
                )
            return stored

        return await self._run(uow, tenant_id, project_id, _op)

    async def attempt_advance(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        requested_mode: RoutingMode,
        current_mode: RoutingMode | None = None,
        thresholds: ActivationThresholds | None = None,
        canary_fraction: float | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> ActivationVerdict:
        """Refuse a learned-mode advance when Chapter 6.9 gates are unmet.

        Durable `routing.mode` is the current mode; a caller cannot skip
        by passing a later value. Calibration comes from the frozen fit's
        holdout Brier/ECE (not RouteDecision.predicted_success, which
        remains null per EDR-0005).
        """

        async def _op(active: PostgresUnitOfWork) -> ActivationVerdict:
            state = await self._policies.get_activation(
                active.connection, tenant_id=tenant_id, project_id=project_id
            )
            durable: RoutingMode = (
                state.routing_mode if state is not None else "deterministic"
            )
            if current_mode is not None and current_mode != durable:
                raise DdeError(
                    "POLICY_DENIED",
                    "stale routing.mode; durable current does not match caller",
                    details={
                        "durable_mode": durable,
                        "supplied_mode": current_mode,
                    },
                )
            if requested_mode == durable and state is not None:
                return ActivationVerdict(
                    allowed=True,
                    requested_mode=requested_mode,
                    current_mode=durable,
                    gates=(),
                    refused_reasons=(),
                )
            records = await self._repository.list_real_eligible_population(
                active.connection, tenant_id=tenant_id, project_id=project_id
            )
            workload_classes: list[str] = []
            for row in records:
                if row.route_decision_id is None:
                    continue
                decision = await self._routes.get_route_decision(
                    active.connection, row.route_decision_id
                )
                if decision is not None:
                    workload_classes.append(decision.workload_class)
            policy = await self._policies.get_latest(
                active.connection, tenant_id=tenant_id, project_id=project_id
            )
            safety_regressions = sum(
                1
                for row in records
                if row.routing_policy_version.startswith("frozen:")
                and row.failure_attribution == "route_attributable"
                and row.observed_outcome_vector.get("actual_verified_outcome")
                == "FAILED"
            )
            verdict = evaluate_activation_gates(
                records=records,
                workload_classes=workload_classes,
                current_mode=durable,
                requested_mode=requested_mode,
                thresholds=thresholds,
                brier=None if policy is None else policy.brier,
                ece=None if policy is None else policy.ece,
                holdout_regression=(
                    None if policy is None else policy.holdout_regression
                ),
                safety_regressions=safety_regressions,
                fallback_robustness_demonstrated=(
                    False if policy is None else policy.fallback_robustness_demonstrated
                ),
                drift_within_bounds=(
                    None if policy is None else policy.drift_within_bounds
                ),
                offline_fit_exists=policy is not None
                and policy.fit_kind == "frozen_full_information",
                frozen_exploitation=True
                if policy is None
                else not policy.continued_update,
                beats_constant_policy=(
                    None if policy is None else policy.beats_constant_policy
                ),
            )
            if not verdict.allowed:
                raise DdeError(
                    "POLICY_DENIED",
                    "learning activation gates unmet; routing.mode unchanged",
                    details={
                        "current_mode": durable,
                        "requested_mode": requested_mode,
                        "refused_reasons": list(verdict.refused_reasons),
                    },
                )
            now = _now(self._clock)
            fraction = (
                canary_fraction
                if canary_fraction is not None
                else (
                    float(state.canary_fraction)
                    if state is not None
                    else DEFAULT_CANARY_FRACTION
                )
            )
            last_mode: RoutingMode = (
                state.last_certified_mode if state is not None else "deterministic"
            )
            last_policy_id = (
                state.last_certified_policy_id if state is not None else None
            )
            active_policy_id = policy.policy_id if policy is not None else None
            if requested_mode == "promoted_historical" and policy is not None:
                await self._policies.update_status(
                    active.connection,
                    policy_id=policy.policy_id,
                    status="certified",
                )
                last_mode = "promoted_historical"
                last_policy_id = policy.policy_id
            written = RoutingActivationState(
                activation_id=(state.activation_id if state is not None else uuid7()),
                tenant_id=tenant_id,
                project_id=project_id,
                routing_mode=requested_mode,
                active_policy_id=active_policy_id,
                last_certified_policy_id=last_policy_id,
                last_certified_mode=last_mode,
                canary_fraction=fraction,
                continued_update_enabled=False,
                created_at=(state.created_at if state is not None else now),
                updated_at=now,
            )
            await self._policies.upsert_activation(active.connection, written)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="RoutingModeAdvanced",
                aggregate_type="routing_activation_state",
                aggregate_id=written.activation_id,
                payload={
                    "from_mode": durable,
                    "to_mode": requested_mode,
                    "active_policy_id": (
                        str(active_policy_id) if active_policy_id else None
                    ),
                },
                uow=active,
            )
            return verdict

        return await self._run(uow, tenant_id, project_id, _op)

    async def rollback(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> RoutingActivationState:
        """ROLLBACK: return to the last certified policy, never untested.

        The frozen artifact remains deployable (not deleted). Idempotent
        when already on the certified mode.
        """

        async def _op(active: PostgresUnitOfWork) -> RoutingActivationState:
            state = await self._policies.get_activation(
                active.connection, tenant_id=tenant_id, project_id=project_id
            )
            current: RoutingMode = (
                state.routing_mode if state is not None else "deterministic"
            )
            certified = last_certified_mode(
                current=current,
                certified=(None if state is None else state.last_certified_mode),
            )
            now = _now(self._clock)
            target_policy = None if state is None else state.last_certified_policy_id
            if certified == "deterministic":
                target_policy = None
            written = RoutingActivationState(
                activation_id=(state.activation_id if state is not None else uuid7()),
                tenant_id=tenant_id,
                project_id=project_id,
                routing_mode=certified,
                active_policy_id=target_policy,
                last_certified_policy_id=(
                    None if state is None else state.last_certified_policy_id
                ),
                last_certified_mode=certified,
                canary_fraction=(
                    float(state.canary_fraction)
                    if state is not None
                    else DEFAULT_CANARY_FRACTION
                ),
                continued_update_enabled=False,
                created_at=state.created_at if state is not None else now,
                updated_at=now,
            )
            stored = await self._policies.upsert_activation(active.connection, written)
            if current != certified:
                await self._events.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    event_type="RoutingModeRolledBack",
                    aggregate_type="routing_activation_state",
                    aggregate_id=stored.activation_id,
                    payload={
                        "from_mode": current,
                        "to_mode": certified,
                        "last_certified_policy_id": (
                            str(stored.last_certified_policy_id)
                            if stored.last_certified_policy_id
                            else None
                        ),
                    },
                    uow=active,
                )
            return stored

        return await self._run(uow, tenant_id, project_id, _op)

    async def attempt_online_update(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> None:
        """Partial-information path. Unreachable until frozen fit exists,
        continued_update is explicitly enabled, and that switch has its
        own canary evidence. No updater is implemented in this mission.
        """

        async def _op(active: PostgresUnitOfWork) -> None:
            state = await self._policies.get_activation(
                active.connection, tenant_id=tenant_id, project_id=project_id
            )
            policy = await self._policies.get_latest(
                active.connection, tenant_id=tenant_id, project_id=project_id
            )
            raise DdeError(
                "POLICY_DENIED",
                "partial-information online update is unreachable",
                details={
                    "frozen_fit_exists": policy is not None,
                    "continued_update_enabled": (
                        False if state is None else state.continued_update_enabled
                    ),
                    "reason": "no_online_updater",
                },
            )

        await self._run(uow, tenant_id, project_id, _op)


def _policy_from_fit(
    fit: FrozenFit,
    *,
    tenant_id: UUID,
    project_id: UUID,
    learning_run_id: UUID,
    now: datetime,
) -> LearnedRoutingPolicy:
    return LearnedRoutingPolicy(
        policy_id=uuid7(),
        tenant_id=tenant_id,
        project_id=project_id,
        learning_run_id=learning_run_id,
        fit_kind="frozen_full_information",
        policy_hash=fit.policy_hash,
        mapping=dict(fit.mapping),
        constant_policy_profile_id=fit.constant_policy_profile_id,
        train_count=fit.train_count,
        holdout_count=fit.holdout_count,
        brier=fit.brier,
        ece=fit.ece,
        holdout_learner_expected=fit.holdout_learner_expected,
        holdout_constant_expected=fit.holdout_constant_expected,
        holdout_incumbent_success=fit.holdout_incumbent_success,
        beats_constant_policy=fit.beats_constant_policy,
        holdout_regression=fit.holdout_regression,
        drift_within_bounds=fit.drift_within_bounds,
        continued_update=False,
        status="fitted",
        training_experience_ids=list(fit.training_experience_ids),
        fallback_robustness_demonstrated=fit.fallback_robustness_demonstrated,
        created_at=now,
        updated_at=now,
    )


def _fallback_robustness(observations: list[OutcomeObservation]) -> bool:
    """Structurally: a learned profile is applied only among survivors.
    Demonstrate by evicting every mapped profile at gate 5 and asserting
    evaluate() never selects an evicted one."""
    profiles = {row.selected_profile_id for row in observations}
    if not profiles:
        return False
    now = datetime.now(UTC)
    task = Task.model_validate(
        {
            "task_id": uuid7(),
            "tenant_id": uuid7(),
            "project_id": uuid7(),
            "mission_id": uuid7(),
            "graph_id": uuid7(),
            "title": "fallback-robustness",
            "intent": "outage",
            "task_class": "implementation",
            "requirement_refs": ["REQ-1"],
            "feature_refs": [],
            "success_criteria": ["c"],
            "expected_write_scope": ["engine/routing"],
            "expected_read_scope": [],
            "blast_radius": "local",
            "risk_class": "low",
            "estimated_effort": "s",
            "autonomy_ceiling": 2,
            "requires_approval": False,
            "status": "CREATED",
            "lock_version": 1,
            "created_at": now,
            "updated_at": now,
        }
    )
    result = evaluate(task, health_evicted_profiles=frozenset(profiles))
    return result.selected_profile_id not in profiles and (
        result.selected_profile_id == HUMAN_DECISION_TASK
        or "HEALTH_EVICTED" in ",".join(result.reason_codes)
        or result.selected_profile_id not in profiles
    )
