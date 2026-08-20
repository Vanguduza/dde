"""Chapter 7.1's deterministic Execution Planner steps, as a pure function
— mirrors `engine.routing.rules.evaluate`'s split between policy-table
lookups (`engine.execution.policy`) and the pure decision function tested
independently of PostgreSQL.

Chapter 7.1 lists the Execution Planner's steps as: "verify the profile is
certified for the exact model+harness+toolset+environment tuple · select a
compatible environment · allocate a workspace · resolve capabilities to
implementations · request minimum leases · bind context and oracle ·
compute budgets · select policy-permitted fallbacks · hash and persist
before execution." This module computes everything that step list assigns
to *this task's declared data* (budgets, capability pass-through,
enforcement tier, policy fields); `engine.execution.service.
ExecutionPlanService` performs the steps that require I/O (environment
provisioning, hashing, persistence) around it.

Explicitly not implemented, because the certifying registry does not exist
yet (Chapter 8/DDE-011): "verify the profile is certified". "select
policy-permitted fallbacks" is also not implemented — `ExecutionPlan` (Ch.7.1's
own field list) carries no `fallback_plan` column the way `RouteDecision`
does, so there is no field to populate.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.contracts.route_decision import RouteDecision
from engine.contracts.task import Task
from engine.environments.service import EnvironmentClass
from engine.execution.policy import (
    ENFORCEMENT_TIER,
    ENVIRONMENT_CLASS,
    budget_for_effort,
    checkpoint_policy_json,
    escalation_policy_json,
    retry_policy_json,
)


@dataclass(frozen=True)
class PlannedExecution:
    """Everything `ExecutionPlanService.plan()` needs that does not require
    provisioning I/O."""

    environment_class: EnvironmentClass
    capability_requirements: list[str]
    enforcement_tier: str
    autonomy_level: int
    resource_budget: dict[str, object]
    time_budget: dict[str, object]
    token_budget: dict[str, object]
    checkpoint_policy: dict[str, object]
    retry_policy: dict[str, object]
    escalation_policy: dict[str, object]


def plan_execution(*, task: Task, route_decision: RouteDecision) -> PlannedExecution:
    """Chapter 7.1's "compute budgets" and the fields it does not require
    I/O for. `capability_requirements` is `route_decision.
    required_capabilities` passed straight through (Chapter 7's brief:
    "wire it to real upstream data ... rather than inventing new fields")."""
    budget = budget_for_effort(task.estimated_effort)
    return PlannedExecution(
        environment_class=ENVIRONMENT_CLASS,
        capability_requirements=list(route_decision.required_capabilities),
        enforcement_tier=ENFORCEMENT_TIER,
        autonomy_level=task.autonomy_ceiling,
        resource_budget={
            "cpu_seconds": budget.cpu_seconds,
            "memory_mb": budget.memory_mb,
        },
        time_budget={"wall_clock_seconds": budget.wall_clock_seconds},
        token_budget={"max_tokens": budget.max_tokens},
        checkpoint_policy=checkpoint_policy_json(),
        retry_policy=retry_policy_json(),
        escalation_policy=escalation_policy_json(),
    )
