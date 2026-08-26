"""Production Chapter 5.13 context-policy activation mutations (DDE-059).

Call sites:

- `evaluate_candidate()` -- runs `PromotionGateService.evaluate` for a
  first-class arm (`pull` / `push` / `semantic`) against the certified
  Stage 1 baseline. Does not flip `compile()`.
- `attempt_advance()` -- the sole writer that may request a forward
  `context.mode` change. Reads the durable current mode (a caller cannot
  skip). Shadow is observation-only. Canary and promoted require a
  promotion run whose deferred gates are empty; PARTIAL_PASS is refused.
- `rollback()` -- reachable from any mode; returns to the last certified
  policy (Stage 1 pull when none is certified) and never to an untested
  arm.

`ContextService.compile()` is the production reader of activation state.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.context.activation import (
    DEFAULT_CANARY_FRACTION,
    ActivationVerdict,
    ContextArm,
    ContextMode,
    evaluate_activation_gates,
    last_certified_mode,
)
from engine.context.activation_repository import ContextActivationRepository
from engine.context.eval_repository import PromotionGateRunRepository
from engine.context.promotion import PromotionGateService
from engine.context.service import ContextService
from engine.contracts.context_activation_state import ContextActivationState
from engine.contracts.promotion_gate_run import PromotionGateRun
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")


def _now(clock: Clock) -> datetime:
    stamped = clock.now()
    if stamped.tzinfo is None:
        return stamped.replace(tzinfo=UTC)
    return stamped


class ContextActivationService:
    """Evaluates Chapter 5.13 gates and persists context.mode state."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: ContextActivationRepository | None = None,
        runs: PromotionGateRunRepository | None = None,
        promotion: PromotionGateService | None = None,
        events: EventService | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or ContextActivationRepository()
        self._runs = runs or PromotionGateRunRepository()
        self._promotion = promotion or PromotionGateService(engine)
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

    async def evaluate_candidate(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_arm: ContextArm,
        idempotency_key: str,
        root: Path,
        uow: PostgresUnitOfWork | None = None,
    ) -> PromotionGateRun:
        """Run Chapter 5.13 gates for one arm vs certified pull baseline.

        Both services compile with `respect_activation=False` so an
        in-flight canary cannot contaminate the A/B.
        """
        baseline = ContextService(
            self._engine,
            root=root,
            policy_arm="pull",
            semantic_retrieval_enabled=False,
        )
        candidate = ContextService(
            self._engine,
            root=root,
            policy_arm="push" if candidate_arm == "push" else "pull",
            semantic_retrieval_enabled=candidate_arm == "semantic",
        )
        return await self._promotion.evaluate(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_label=f"arm:{candidate_arm}",
            idempotency_key=idempotency_key,
            baseline_service=baseline,
            candidate_service=candidate,
            uow=uow,
        )

    async def attempt_advance(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        requested_mode: ContextMode,
        candidate_arm: ContextArm,
        current_mode: ContextMode | None = None,
        promotion_run_id: UUID | None = None,
        canary_fraction: float | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> ActivationVerdict:
        """Refuse a canary/promoted advance when Chapter 5.13 is unmet.

        Durable `context.mode` is the current mode; a caller cannot skip
        by passing a later value.
        """

        async def _op(active: PostgresUnitOfWork) -> ActivationVerdict:
            state = await self._repository.get(
                active.connection, tenant_id=tenant_id, project_id=project_id
            )
            durable: ContextMode = (
                state.context_mode if state is not None else "certified_baseline"
            )
            if current_mode is not None and current_mode != durable:
                raise DdeError(
                    "POLICY_DENIED",
                    "stale context.mode; durable current does not match caller",
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
            run: PromotionGateRun | None = None
            if promotion_run_id is not None:
                run = await self._runs.get(active.connection, promotion_run_id)
            elif state is not None and state.last_promotion_run_id is not None:
                run = await self._runs.get(
                    active.connection, state.last_promotion_run_id
                )
            deferred: tuple[str, ...] | None = None
            decision: str | None = None
            implemented_fail = False
            if run is not None:
                decision = run.decision
                raw = run.gate_results.get("deferred_gates")
                if isinstance(raw, list):
                    deferred = tuple(str(item) for item in raw)
                implemented_fail = decision == "FAIL"
            verdict = evaluate_activation_gates(
                current_mode=durable,
                requested_mode=requested_mode,
                candidate_arm=candidate_arm,
                promotion_decision=decision,
                deferred_gates=deferred,
                implemented_gate_fail=implemented_fail,
            )
            if not verdict.allowed:
                raise DdeError(
                    "POLICY_DENIED",
                    "context activation gates unmet; context.mode unchanged",
                    details={
                        "current_mode": durable,
                        "requested_mode": requested_mode,
                        "candidate_arm": candidate_arm,
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
            last_mode: ContextMode = (
                state.last_certified_mode if state is not None else "certified_baseline"
            )
            last_arm: ContextArm = (
                state.last_certified_arm if state is not None else "pull"
            )
            if requested_mode == "promoted":
                last_mode = "promoted"
                last_arm = candidate_arm
            written = ContextActivationState(
                activation_id=(state.activation_id if state is not None else uuid7()),
                tenant_id=tenant_id,
                project_id=project_id,
                context_mode=requested_mode,
                candidate_arm=candidate_arm,
                last_certified_mode=last_mode,
                last_certified_arm=last_arm,
                last_promotion_run_id=(
                    run.run_id
                    if run is not None
                    else (state.last_promotion_run_id if state is not None else None)
                ),
                canary_fraction=fraction,
                created_at=(state.created_at if state is not None else now),
                updated_at=now,
            )
            await self._repository.upsert(active.connection, written)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="ContextModeAdvanced",
                aggregate_type="context_activation_state",
                aggregate_id=written.activation_id,
                payload={
                    "from_mode": durable,
                    "to_mode": requested_mode,
                    "candidate_arm": candidate_arm,
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
    ) -> ContextActivationState:
        """Return to the last certified policy, never an untested arm."""

        async def _op(active: PostgresUnitOfWork) -> ContextActivationState:
            state = await self._repository.get(
                active.connection, tenant_id=tenant_id, project_id=project_id
            )
            now = _now(self._clock)
            certified = last_certified_mode(
                current=(
                    state.context_mode if state is not None else "certified_baseline"
                ),
                certified=(state.last_certified_mode if state is not None else None),
            )
            certified_arm: ContextArm = (
                state.last_certified_arm if state is not None else "pull"
            )
            if certified == "certified_baseline":
                certified_arm = "pull"
            written = ContextActivationState(
                activation_id=(state.activation_id if state is not None else uuid7()),
                tenant_id=tenant_id,
                project_id=project_id,
                context_mode=certified,
                candidate_arm=certified_arm,
                last_certified_mode=certified,
                last_certified_arm=certified_arm,
                last_promotion_run_id=(
                    state.last_promotion_run_id if state is not None else None
                ),
                canary_fraction=(
                    float(state.canary_fraction)
                    if state is not None
                    else DEFAULT_CANARY_FRACTION
                ),
                created_at=(state.created_at if state is not None else now),
                updated_at=now,
            )
            await self._repository.upsert(active.connection, written)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="ContextModeRolledBack",
                aggregate_type="context_activation_state",
                aggregate_id=written.activation_id,
                payload={
                    "to_mode": certified,
                    "to_arm": certified_arm,
                },
                uow=active,
            )
            return written

        return await self._run(uow, tenant_id, project_id, _op)
