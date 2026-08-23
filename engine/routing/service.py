"""Production Routing Intelligence — the sole writer of `route_decisions`
rows in PostgreSQL (Chapter 2.6, 3.5, 3.8, 6.1-6.3).

`RouterService.route()` runs Chapter 6.1's deterministic v1 pipeline
(`engine.routing.rules.evaluate`, Chapter 6.2) against an already-persisted
`Task` and commits the outcome — including a genuine `NO_ELIGIBLE_WORKER`
escalation, which is a real, persisted RouteDecision (Chapter 6.1 gate 9),
not an exception — as an immutable `route_decisions` row (Chapter 3.8:
RouteDecision "Mutable after creation: Immutable"; Chapter 3.10: its
definition carries a `decision_hash` and is never versioned the way
ContextPackage/TaskGraph are — `schemas/objects/route_decision.json` has
no `version` column, so each `route()` call inserts one independent,
append-only row).

Deliberately out of Stage 1 scope, per the mission brief: Chapter 8's
certified-profile registry (DDE-011 — `engine.routing.registry` is an
explicitly flagged, minimal stand-in, never that registry), and real
performance/cost *predictions* (`predicted_success`, `predicted_cost`,
`predicted_latency`, `confidence` are left `None` -- Chapter 6.5's real
outcome telemetry now exists, `engine.telemetry`/DDE-035, but nothing
fits a prediction model against it yet). The Route Critic (triggered-only,
Chapter 6.6) and real exploration (Chapter 6.7 — `selection_propensity`
is `1.0` on every decision, exactly as Chapter 6.3 states: "1.0 for
deterministic selections"; epsilon defaults to 0 until a tenant
explicitly enables it, which Stage 1 never does) remain deferred for the
same reason, named in
`docs/truth/edr/EDR-0005-routing-telemetry-partial-implementation.md`.
Appendix A provider-agnostic model selection IS wired as an explicit
per-call opt-in (`model_mode="off" | "auto" | "fixed"`, with
`model_fixed_id`/`model_fixed_provider` pinning any declared provider in
fixed mode). It annotates which declared model a surviving harness profile
would call and never alters gate outcomes; nothing makes a live provider
call — adapters remain fail-closed until the broker wires credentials
(EDR-0001 Path B).
Learning/promotion (Chapter 6.8-6.9, DDE-057/058) is separately out of
scope.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Literal, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.route_decision import RouteDecision
from engine.contracts.task import Task
from engine.core.clock import Clock, SystemClock
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.routing.hashing import decision_hash
from engine.routing.health import (
    compute_model_health,
    health_samples_from_outcomes,
    thresholds_from_policy_overrides,
)
from engine.routing.policy import POLICY_VERSION, escalation_plan_json
from engine.routing.registry import resolve_model_selection
from engine.routing.repository import RouteDecisionRepository
from engine.routing.rules import (
    HEALTH_EVICTED_REASON_CODE,
    evaluate,
)
from engine.telemetry.repository import RoutingDecisionOutcomeRepository
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")

SELECTION_SOURCE: Literal["deterministic"] = "deterministic"
DETERMINISTIC_SELECTION_PROPENSITY = 1.0


class RouterService:
    """Async, PostgreSQL-backed writer for `route_decisions` (Chapter
    3.8). Each public method opens and commits its own unit of work unless
    one is supplied, so a caller composing a cross-module transaction
    (Chapter 3.5) can share it instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        events: EventService | None = None,
        repository: RouteDecisionRepository | None = None,
        clock: Clock | None = None,
        outcomes: RoutingDecisionOutcomeRepository | None = None,
        health_policy_overrides: Mapping[str, object] | None = None,
    ) -> None:
        self._engine = engine
        self._events = events or EventService(engine)
        self._repository = repository or RouteDecisionRepository()
        self._clock = clock or SystemClock()
        self._outcomes = outcomes or RoutingDecisionOutcomeRepository()
        self._health_thresholds = thresholds_from_policy_overrides(
            health_policy_overrides
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

    async def route(
        self,
        *,
        task: Task,
        workload_class: str | None = None,
        previous_generator_profile_id: str | None = None,
        certification_statuses: Mapping[str, str] | None = None,
        routing_environment_class: str = "development",
        approval_satisfied: bool = False,
        uow: PostgresUnitOfWork | None = None,
        model_mode: str | None = None,
        model_fixed_id: str | None = None,
        model_fixed_provider: str | None = None,
    ) -> RouteDecision:
        """Compile and persist a new, immutable `RouteDecision` for `task`
        (Chapter 3.9 step 6). Takes an already-materialised `Task` rather
        than a bare `task_id`, matching `ContextService.compile()`'s
        pattern for the identical reason: `engine.missions` has no
        get-by-`task_id` read method, and this mission's brief forbids
        adding one beyond calling `engine.missions`' existing public
        surface.

        `model_mode` ("off" | "auto" | "fixed", with `model_fixed_id` and
        `model_fixed_provider` for "fixed") opts a single decision into
        provider-agnostic model selection; `None` keeps the exact
        pre-selection behaviour. The selection only annotates surviving
        candidates with the declared model a harness profile would call —
        it never changes gate outcomes, and no live provider call is made
        (adapters fail-closed pending broker credentials, EDR-0001 Path B).

        Health-based eviction (adoption #4): before evaluating, the most
        recent recorded `routing_decision_outcomes` (Chapter 6.5) are read
        and reduced to a per-profile rolling health verdict. Profiles
        breaching the failure-rate threshold are hard-eliminated at gate 5
        and the selection falls through to the next `prefer[]` entry; the
        eviction is recorded as a typed `HEALTH_EVICTED:<profiles>` reason
        code on the decision and a `ModelHealthEvicted` event. The window
        self-clears as healthy outcomes accumulate, so expiry needs no
        policy edit."""
        tenant_id = task.tenant_id
        project_id = task.project_id
        mission_id = task.mission_id
        selection_directive = (
            None
            if model_mode is None
            else resolve_model_selection(
                model_mode, model_fixed_id, model_fixed_provider
            )
        )

        async def _op(active: PostgresUnitOfWork) -> RouteDecision:
            recent = await self._outcomes.list_recent_with_selected_profiles(
                active.connection,
                tenant_id=tenant_id,
                project_id=project_id,
            )
            health_report = compute_model_health(
                health_samples_from_outcomes(recent),
                thresholds=self._health_thresholds,
            )
            health_evicted_profiles = health_report.unhealthy_profiles()
            result = evaluate(
                task,
                workload_class=workload_class,
                previous_generator_profile_id=previous_generator_profile_id,
                certification_statuses=certification_statuses,
                routing_environment_class=routing_environment_class,
                approval_satisfied=approval_satisfied,
                model_selection=selection_directive,
                health_evicted_profiles=health_evicted_profiles,
            )
            candidates_json = [candidate.to_json() for candidate in result.candidates]
            required_capabilities = list(result.required_capabilities)
            reason_codes = list(result.reason_codes)
            if health_evicted_profiles:
                reason_codes.append(
                    f"{HEALTH_EVICTED_REASON_CODE}:"
                    + ",".join(sorted(health_evicted_profiles))
                )
            fallback_plan = [dict(entry) for entry in result.fallback_plan]
            escalation_plan = escalation_plan_json()
            digest = decision_hash(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                task_id=task.task_id,
                candidates=candidates_json,
                selected_worker_profile_id=result.selected_profile_id,
                workload_class=result.workload_class,
                required_capabilities=required_capabilities,
                required_environment_class=result.required_environment_class,
                reason_codes=reason_codes,
                selection_source=SELECTION_SOURCE,
                selection_propensity=DETERMINISTIC_SELECTION_PROPENSITY,
                fallback_plan=fallback_plan,
                escalation_plan=escalation_plan,
                policy_version=POLICY_VERSION,
            )
            now = self._clock.now()
            decision = RouteDecision(
                decision_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                task_id=task.task_id,
                candidates=candidates_json,
                selected_worker_profile_id=result.selected_profile_id,
                workload_class=result.workload_class,
                required_capabilities=required_capabilities,
                required_environment_class=result.required_environment_class,
                reason_codes=reason_codes,
                predicted_success=None,
                predicted_cost=None,
                predicted_latency=None,
                confidence=None,
                selection_source=SELECTION_SOURCE,
                selection_propensity=DETERMINISTIC_SELECTION_PROPENSITY,
                fallback_plan=fallback_plan,
                escalation_plan=escalation_plan,
                policy_version=POLICY_VERSION,
                decision_hash=digest,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_route_decision(active.connection, decision)
            if health_evicted_profiles:
                # One event per evicted profile: aggregate_id is a UUID
                # column (Chapter 3.7), so the profile id rides in payload.
                for profile_id in sorted(health_evicted_profiles):
                    await self._events.append(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        event_type="ModelHealthEvicted",
                        aggregate_type="worker_profile",
                        aggregate_id=uuid7(),
                        mission_id=mission_id,
                        task_id=task.task_id,
                        payload={
                            "evicted_worker_profile_id": profile_id,
                            "evicted_worker_profile_ids": sorted(
                                health_evicted_profiles
                            ),
                            "route_decision_id": str(decision.decision_id),
                            "reason_code": HEALTH_EVICTED_REASON_CODE,
                        },
                        uow=active,
                    )
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="RouteDecisionCommitted",
                aggregate_type="route_decision",
                aggregate_id=decision.decision_id,
                mission_id=mission_id,
                task_id=task.task_id,
                payload={
                    "workload_class": decision.workload_class,
                    "selected_worker_profile_id": decision.selected_worker_profile_id,
                    "reason_codes": decision.reason_codes,
                    "decision_hash": digest,
                },
                uow=active,
            )
            return decision

        return await self._run(uow, tenant_id, project_id, _op)

    async def get_route_decision(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        decision_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> RouteDecision | None:
        async def _op(active: PostgresUnitOfWork) -> RouteDecision | None:
            return await self._repository.get_route_decision(
                active.connection, decision_id
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def list_for_task(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        task_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[RouteDecision]:
        async def _op(active: PostgresUnitOfWork) -> list[RouteDecision]:
            return await self._repository.list_for_task(active.connection, task_id)

        return await self._run(uow, tenant_id, project_id, _op)
