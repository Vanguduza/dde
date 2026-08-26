"""Production Chapter 6.4 Routing Simulation Model -- the sole writer of
`routing_simulation_runs` rows in PostgreSQL (Chapter 2.6, 3.5, 3.8).

`RoutingSimulationService.run_regression()` is the real production
mutation call site: an operator or CI job supplies a `seed` and the
`scenario_classes` to stress-test, this module drives each real class
through `engine.simulation.scenarios.run_scenario()` (which itself only
ever calls the pure, side-effect-free `engine.routing.rules.evaluate()`
-- never `engine.routing.service.RouterService.route()`), and persists
one durable `RoutingSimulationRun` row summarising every result.

Guarded by `engine.events.idempotency.CommandLedger` on a caller-supplied
`idempotency_key`, the same durable-identity pattern
`engine.verification.runner` uses (AGENTS.md: "New async operation has a
durable identity, an idempotency key and observable state") -- a
repeated invocation with the same key never re-runs the regression, it
returns the first call's stored, completed `RoutingSimulationRun`
instead.

**Never an authority.** This module never calls `RouterService.route()`
and therefore never writes a `route_decisions` row; `disclosed_gaps`
names every requested `scenario_class` this Stage 1 slice cannot
generate a real fixture for; `experience_origin` is hard-coded to
`simulation` and `excluded_from_routing_learning` is hard-coded to
`True` on every row -- Chapter 6.4's "excluded by construction" holds by
construction, not by a caller's discretion.

**Not a registered Capability.** `RoutingSimulationService` is an
internal engine regression/stress-testing tool invoked by an operator or
CI, never a `Capability` a worker leases through the broker (Chapter
9.3) -- `side_effect_class` does not apply here for the same reason it
does not apply to `engine.verification.runner`'s own checks.

**Shadow-mode policy promotion** (`evaluate_shadow_promotion`,
comparable-systems adoption #8) extends this service with offline
candidate-policy evaluation over recorded Chapter 6.5 telemetry. It is
shadow evaluation only: live routing policy selection is neither read
nor written -- see that method's docstring for the full constraint.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.command_idempotency import CommandIdempotency
from engine.contracts.routing_decision_outcome import RoutingDecisionOutcome
from engine.contracts.routing_simulation_run import RoutingSimulationRun
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.hashing import canonical_json, sha256_hex
from engine.core.ids import uuid7
from engine.events.idempotency import CommandLedger
from engine.events.service import EventService
from engine.learning.service import ExperienceRecordService
from engine.routing.policy import POLICY_VERSION
from engine.simulation.repository import RoutingSimulationRunRepository
from engine.simulation.scenarios import (
    DEFERRED_SCENARIO_CLASSES,
    REAL_SCENARIO_CLASSES,
    run_scenario,
)
from engine.simulation.shadow_promotion import (
    SHADOW_PROMOTION_RUN_KIND,
    PolicyMetrics,
    ShadowPromotionDecision,
    ShadowPromotionRequest,
)
from engine.simulation.shadow_promotion import (
    evaluate_shadow_promotion as _evaluate_shadow_promotion,
)
from engine.telemetry.tables import routing_decision_outcomes
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")

#: Identifies this deterministic fixture generator, never a trained
#: model -- Chapter 6.4: "model versions are persisted for
#: reproducibility." Bump only when `engine.simulation.scenarios`'s real
#: fixture-generation logic changes.
MODEL_VERSION = "rsm-fixture-generator-v1"


def _run_request_hash(*, seed: str, scenario_classes: tuple[str, ...]) -> str:
    return sha256_hex(
        canonical_json({"seed": seed, "scenario_classes": list(scenario_classes)})
    )


def _metrics_payload(metrics: PolicyMetrics) -> dict[str, Any]:
    """Serialize one policy's measured metrics for the JSONB payload."""
    return {
        "decisions": metrics.decisions,
        "successes": metrics.successes,
        "wasted_accepts": metrics.wasted_accepts,
        "missed_passes": metrics.missed_passes,
        "correct_rejections": metrics.correct_rejections,
        "routed_rate": metrics.routed_rate,
        "success_yield": metrics.success_yield,
        "wasted_accept_rate": metrics.wasted_accept_rate,
        "gate_fail_rate": metrics.gate_fail_rate,
        "mean_cost_seconds": metrics.mean_cost,
        "cost_samples": metrics.cost_samples,
    }


def _metrics_from_payload(payload: dict[str, Any]) -> PolicyMetrics:
    return PolicyMetrics(
        decisions=int(payload["decisions"]),
        successes=int(payload["successes"]),
        wasted_accepts=int(payload["wasted_accepts"]),
        missed_passes=int(payload["missed_passes"]),
        correct_rejections=int(payload["correct_rejections"]),
        routed_rate=float(payload["routed_rate"]),
        success_yield=float(payload["success_yield"]),
        wasted_accept_rate=float(payload["wasted_accept_rate"]),
        gate_fail_rate=float(payload["gate_fail_rate"]),
        mean_cost=payload["mean_cost_seconds"],
        cost_samples=int(payload["cost_samples"]),
    )


def _decision_from_run(run: RoutingSimulationRun) -> ShadowPromotionDecision:
    """Rehydrate the measured verdict from a replayed idempotent run row.
    The decision is fully derived from the persisted `scenario_results`
    payload -- never recomputed from possibly-changed telemetry."""
    result = run.scenario_results[0]
    baseline = cast("dict[str, Any]", result["baseline_metrics"])
    candidate = cast("dict[str, Any]", result["candidate_metrics"])
    deltas = cast("dict[str, Any]", result["deltas"])
    return ShadowPromotionDecision(
        promoted=bool(result["passed"]),
        baseline=_metrics_from_payload(baseline),
        candidate=_metrics_from_payload(candidate),
        success_yield_delta=float(deltas["success_yield_delta"]),
        routed_rate_delta=float(deltas["routed_rate_delta"]),
        wasted_accept_delta=float(deltas["wasted_accept_delta"]),
        cost_delta=deltas["cost_delta_seconds"],
        gate_fail_delta=float(deltas["gate_fail_delta"]),
        cost_basis=str(result["cost_basis"]),
        reasons=cast("list[str]", result["reasons"]),
        rollback_trigger_fired=bool(result["rollback_trigger_fired"]),
    )


class RoutingSimulationService:
    """Async, PostgreSQL-backed writer for `routing_simulation_runs`
    (Chapter 3.8). Each public method opens and commits its own unit of
    work unless one is supplied, so a caller composing a cross-module
    transaction (Chapter 3.5) can share it instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        events: EventService | None = None,
        commands: CommandLedger | None = None,
        repository: RoutingSimulationRunRepository | None = None,
        learning: ExperienceRecordService | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._events = events or EventService(engine)
        self._commands = commands or CommandLedger(engine)
        self._repository = repository or RoutingSimulationRunRepository()
        self._clock = clock or SystemClock()
        self._learning = learning or ExperienceRecordService(
            engine, events=self._events, clock=self._clock
        )

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

    async def run_regression(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        seed: str,
        scenario_classes: tuple[str, ...],
        idempotency_key: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> RoutingSimulationRun:
        """Chapter 6.4: run every real scenario class in
        `scenario_classes` against the real `engine.routing.rules`
        pipeline and persist one durable, reproducible summary row."""
        if not scenario_classes:
            raise DdeError(
                "POLICY_DENIED",
                "at least one scenario_class is required",
                retryable=False,
            )
        unknown = [
            item
            for item in scenario_classes
            if item not in REAL_SCENARIO_CLASSES
            and item not in DEFERRED_SCENARIO_CLASSES
        ]
        if unknown:
            raise DdeError(
                "POLICY_DENIED",
                "unknown scenario class requested",
                retryable=False,
                details={"unknown": unknown},
            )
        request_hash = _run_request_hash(seed=seed, scenario_classes=scenario_classes)

        async def _op(active: PostgresUnitOfWork) -> RoutingSimulationRun:
            record, is_new = await self._commands.begin(
                tenant_id=tenant_id,
                project_id=project_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                uow=active,
            )
            if not is_new:
                return self._replay_or_raise(record)

            scenario_results = []
            disclosed_gaps = []
            for scenario_class in scenario_classes:
                if scenario_class in DEFERRED_SCENARIO_CLASSES:
                    disclosed_gaps.append(
                        f"{scenario_class}: no real, un-fabricated fixture in Stage 1 "
                        "-- see EDR-0006-routing-simulation-fixture-generator-"
                        "partial-scope"
                    )
                    continue
                result = run_scenario(
                    scenario_class,
                    seed=seed,
                    tenant_id=tenant_id,
                    project_id=project_id,
                )
                scenario_results.append(result.to_json())

            now = self._clock.now()
            run = RoutingSimulationRun(
                run_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                seed=seed,
                policy_version=POLICY_VERSION,
                model_version=MODEL_VERSION,
                scenario_classes=list(scenario_classes),
                scenario_results=scenario_results,
                experience_origin="simulation",
                excluded_from_routing_learning=True,
                disclosed_gaps=disclosed_gaps,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_run(active.connection, run)
            await self._learning.record_from_simulation(run=run, uow=active)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="RoutingSimulationRunRecorded",
                aggregate_type="routing_simulation_run",
                aggregate_id=run.run_id,
                mission_id=None,
                task_id=None,
                payload={
                    "seed": seed,
                    "scenario_classes": list(scenario_classes),
                    "disclosed_gaps": disclosed_gaps,
                },
                uow=active,
            )
            await self._commands.complete(
                tenant_id=tenant_id,
                project_id=project_id,
                command_id=record.command_id,
                result=run.model_dump(mode="json"),
                uow=active,
            )
            return run

        return await self._run(uow, tenant_id, project_id, _op)

    def _replay_or_raise(self, record: CommandIdempotency) -> RoutingSimulationRun:
        if record.status == "completed" and record.result is not None:
            return RoutingSimulationRun.model_validate(record.result)
        if record.status == "failed":
            raise DdeError(
                "VERSION_CONFLICT",
                "Command previously failed; refusing to re-execute",
                details={"idempotency_key": record.idempotency_key},
            )
        raise DdeError(
            "VERSION_CONFLICT",
            "Command is already in progress",
            retryable=True,
            details={"idempotency_key": record.idempotency_key},
        )

    async def get_run(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        run_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> RoutingSimulationRun | None:
        async def _op(active: PostgresUnitOfWork) -> RoutingSimulationRun | None:
            return await self._repository.get_run(active.connection, run_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def evaluate_shadow_promotion(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        request: ShadowPromotionRequest,
        idempotency_key: str,
        outcomes: list[RoutingDecisionOutcome] | None = None,
        seed: str = "shadow",
        uow: PostgresUnitOfWork | None = None,
    ) -> tuple[RoutingSimulationRun, ShadowPromotionDecision]:
        """Shadow-mode policy promotion over recorded Chapter 6.5 telemetry.

        **Shadow evaluation only.** This method never touches live routing
        policy selection -- `engine.routing`'s decision path is neither
        written nor re-ordered here; the only durable effect is a
        `routing_simulation_runs` row with `run_kind="shadow_promotion"`
        (plus its event and command-ledger entries). Promoting a candidate
        into live selection remains a separate, human-governed act outside
        this service.

        The candidate is scored against the real `routing_decision_outcomes`
        rows for `tenant_id`/`project_id` (or the caller-supplied `outcomes`,
        for pure evaluation), producing measured quadrant counts and
        success-yield, wasted-accept, cost and gate-fail deltas. Promotion
        requires: candidate `success_yield` strictly beats baseline AND its
        `wasted_accept_rate` does not regress beyond
        `request.wasted_accept_tolerance` AND cost does not regress within
        `request.max_cost_regression` AND the caller's pre-registered
        rollback trigger stays quiet. Idempotent through the same
        CommandLedger every other mutation in this codebase uses.
        """
        if not request.candidate_policy:
            raise DdeError(
                "POLICY_DENIED",
                "candidate_policy must not be empty",
                retryable=False,
            )
        if not (0.0 <= request.max_cost_regression <= 1.0):
            raise DdeError(
                "POLICY_DENIED",
                "max_cost_regression must be within [0.0, 1.0]",
                retryable=False,
                details={"max_cost_regression": request.max_cost_regression},
            )

        async def _op(
            active: PostgresUnitOfWork,
        ) -> tuple[RoutingSimulationRun, ShadowPromotionDecision]:
            record, is_new = await self._commands.begin(
                tenant_id=tenant_id,
                project_id=project_id,
                idempotency_key=idempotency_key,
                request_hash=sha256_hex(canonical_json(request.candidate_policy)),
                uow=active,
            )
            if not is_new:
                replayed = self._replay_or_raise(record)
                decision = _decision_from_run(replayed)
                return replayed, decision

            if outcomes is None:
                result = await active.connection.execute(
                    select(routing_decision_outcomes)
                    .where(
                        routing_decision_outcomes.c.tenant_id == tenant_id,
                        routing_decision_outcomes.c.project_id == project_id,
                    )
                    .order_by(routing_decision_outcomes.c.created_at.asc())
                )
                recorded = [
                    RoutingDecisionOutcome.model_validate(dict(row))
                    for row in result.mappings().all()
                ]
            else:
                recorded = outcomes

            decision = _evaluate_shadow_promotion(request, recorded)

            now = self._clock.now()
            disclosed_gaps = [decision.cost_basis]
            scenario_results: list[dict[str, Any]] = [
                {
                    "scenario_class": SHADOW_PROMOTION_RUN_KIND,
                    "passed": decision.promoted,
                    "baseline_metrics": _metrics_payload(decision.baseline),
                    "candidate_metrics": _metrics_payload(decision.candidate),
                    "quadrants": {
                        "baseline": {
                            "successes": decision.baseline.successes,
                            "wasted_accepts": decision.baseline.wasted_accepts,
                            "missed_passes": decision.baseline.missed_passes,
                            "correct_rejections": (
                                decision.baseline.correct_rejections
                            ),
                        },
                        "candidate": {
                            "successes": decision.candidate.successes,
                            "wasted_accepts": decision.candidate.wasted_accepts,
                            "missed_passes": decision.candidate.missed_passes,
                            "correct_rejections": (
                                decision.candidate.correct_rejections
                            ),
                        },
                    },
                    "deltas": {
                        "success_yield_delta": decision.success_yield_delta,
                        "routed_rate_delta": decision.routed_rate_delta,
                        "wasted_accept_delta": decision.wasted_accept_delta,
                        "cost_delta_seconds": decision.cost_delta,
                        "gate_fail_delta": decision.gate_fail_delta,
                    },
                    "reasons": decision.reasons,
                    "rollback_trigger_fired": decision.rollback_trigger_fired,
                    "cost_basis": decision.cost_basis,
                }
            ]
            run = RoutingSimulationRun(
                run_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                seed=seed,
                policy_version=POLICY_VERSION,
                model_version=MODEL_VERSION,
                scenario_classes=[SHADOW_PROMOTION_RUN_KIND],
                scenario_results=scenario_results,
                experience_origin="simulation",
                excluded_from_routing_learning=True,
                disclosed_gaps=disclosed_gaps,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_run(active.connection, run)
            await self._learning.record_from_simulation(run=run, uow=active)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="RoutingSimulationRunRecorded",
                aggregate_type="routing_simulation_run",
                aggregate_id=run.run_id,
                mission_id=None,
                task_id=None,
                payload={
                    "run_kind": SHADOW_PROMOTION_RUN_KIND,
                    "promoted": decision.promoted,
                    "success_yield_delta": decision.success_yield_delta,
                    "wasted_accept_delta": decision.wasted_accept_delta,
                    "gate_fail_delta": decision.gate_fail_delta,
                    "rollback_trigger_fired": decision.rollback_trigger_fired,
                },
                uow=active,
            )
            await self._commands.complete(
                tenant_id=tenant_id,
                project_id=project_id,
                command_id=record.command_id,
                result=run.model_dump(mode="json"),
                uow=active,
            )
            return run, decision

        return await self._run(uow, tenant_id, project_id, _op)
