"""Production Chapter 6.9 learning-activation mutation (DDE-058).

`attempt_advance()` is the sole writer that may request a `routing.mode`
advance into a learned mode. It reads the Chapter 6.8 eligible
ExperienceRecord population, evaluates Chapter 6.9 gates, and **refuses**
(POLICY_DENIED, no mode change) when any mandatory gate is unmet --
including volume, calibration-without-a-real-score, and illegal skips.
Live `engine.routing.rules` is never mutated here; an allowed verdict is
an auditable decision, not a silent rewrite of the deterministic table.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.core.errors import DdeError
from engine.learning.activation import (
    ActivationVerdict,
    RoutingMode,
    evaluate_activation_gates,
)
from engine.learning.repository import ExperienceRecordRepository
from engine.routing.repository import RouteDecisionRepository
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")


class LearningActivationService:
    """Evaluates Chapter 6.9 gates over the real eligible population."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: ExperienceRecordRepository | None = None,
        routes: RouteDecisionRepository | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or ExperienceRecordRepository()
        self._routes = routes or RouteDecisionRepository()

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

    async def attempt_advance(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        current_mode: RoutingMode,
        requested_mode: RoutingMode,
        uow: PostgresUnitOfWork | None = None,
    ) -> ActivationVerdict:
        """Refuse a learned-mode advance when Chapter 6.9 gates are unmet.

        Calibration Brier/ECE are passed as None until a real prediction
        pipeline exists (EDR-0005: RouteDecision.predicted_success is
        always null) -- insufficient evidence is a refusal, not a pass.
        """

        async def _op(active: PostgresUnitOfWork) -> ActivationVerdict:
            records = await self._repository.list_eligible_for_training(
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
            verdict = evaluate_activation_gates(
                records=records,
                workload_classes=workload_classes,
                current_mode=current_mode,
                requested_mode=requested_mode,
                brier=None,
                ece=None,
                holdout_regression=None,
                fallback_robustness_demonstrated=False,
                drift_within_bounds=None,
                offline_fit_exists=False,
                frozen_exploitation=True,
                beats_constant_policy=None,
            )
            if not verdict.allowed:
                raise DdeError(
                    "POLICY_DENIED",
                    "learning activation gates unmet; routing.mode unchanged",
                    details={
                        "current_mode": current_mode,
                        "requested_mode": requested_mode,
                        "refused_reasons": list(verdict.refused_reasons),
                    },
                )
            return verdict

        return await self._run(uow, tenant_id, project_id, _op)
