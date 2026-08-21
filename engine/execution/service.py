"""Production Execution Planner — the sole writer of `execution_plans` rows
in PostgreSQL (Chapter 3.5, 3.8, 7.1).

`ExecutionPlanService.plan()` runs Chapter 7.1's planner steps against an
already-persisted `Task` (`engine.missions`) and `RouteDecision`
(`engine.routing`), composing `engine.environments.service.
ExecutionEnvironmentService` — the Provisioner — under one shared unit of
work exactly as `engine.missions.service.MissionService.create_task_graph`
composes `engine.planning.service.TaskGraphService` (Chapter 3.5: a
transaction may span module boundaries). It hashes and persists the plan
**before** any workspace exists, matching 7.1's literal step order ("hash
and persist before execution").

**Flagged divergence.** Chapter 7.1's prose lists "allocate a workspace" as
one of the Execution Planner's own steps, but Chapter 3.9's global creation
order places "Workspace allocated, environment leased" at step 9 — *after*
"TaskAttempt created" (step 8), itself after "ExecutionPlan validated and
committed" (step 7). `ExecutionPlan`'s own field list (7.1) has no
`workspace_id` column, only `execution_environment_id` — consistent with
workspace allocation happening later, at attempt-creation time, not at
plan-creation time. This service resolves the tension in favour of 3.9's
explicit ordering: `plan()` acquires the `ExecutionEnvironment` (Chapter 7.4 warm pool:
reuse a pooled READY environment or cold-provision, then lease it `ACTIVE`,
binding `execution_environment_id`) but does not allocate a `Workspace`;
`provision_workspace()` does that separately, standing in for whatever
future `TaskAttempt`-creation caller performs 3.9 step 9 (`TaskAttempt` is
owned by `engine.missions`, out of this mission's scope to create for real).

Deliberately out of Stage 1 scope, per the mission brief: profile
certification (Chapter 8/DDE-011 — `worker_profile_id` is `route_decision.
selected_worker_profile_id`, passed through, never verified against a
certification registry that does not exist), capability-to-implementation
resolution and lease requests (Chapter 9, DDE-016/017 — `acceptance_oracle_
id`/`verification_plan_id` stay `None`), and policy-permitted fallback
selection (`ExecutionPlan` carries no `fallback_plan` column to populate,
unlike `RouteDecision`).

**DDE-013 addition.** Chapter 3.9 step 4 places "WriteScopeLeases reserved
for schedulable tasks" *before* ContextPackage/RouteDecision/ExecutionPlan
(steps 5-7) — the Task Planner's job, not the Execution Planner's. No
`engine.planning` caller reserves one yet (that wiring is a future mission's
job), so `plan()` request the real lease itself, over `task.
expected_write_scope` (Chapter 4.7 rule 3's real field, never invented),
via `engine.integration.service.WriteScopeLeaseService.acquire()` — the
smallest addition that actually populates the already-existing
`write_scope_lease_id` field per this mission's constraint, composing that
sibling service under the same shared unit of work exactly as
`ExecutionEnvironmentService`/`WorkspaceService` already are. Acquisition
is idempotent per `(task_id, scope_patterns)`, so re-planning the same task
never self-conflicts.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.execution_plan import ExecutionPlan
from engine.contracts.route_decision import RouteDecision
from engine.contracts.task import Task
from engine.contracts.workspace import Workspace
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.core.state_machine import transition
from engine.environments.service import ExecutionEnvironmentService
from engine.events.service import EventService
from engine.execution.hashing import plan_hash
from engine.execution.planner import plan_execution
from engine.execution.repository import ExecutionPlanRepository
from engine.execution.states import EXECUTION_PLAN_TRANSITIONS
from engine.integration.service import WriteScopeLeaseService
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work
from engine.workspaces.service import WorkspaceService

T = TypeVar("T")

DEFAULT_WORKSPACE_SIZE_CAP_MB = 2048


class ExecutionPlanService:
    """Async, PostgreSQL-backed writer for `execution_plans` (Chapter 3.8).
    Each public method opens and commits its own unit of work unless one is
    supplied, so a caller composing a cross-module transaction (Chapter
    3.5) can share it instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        events: EventService | None = None,
        repository: ExecutionPlanRepository | None = None,
        environments: ExecutionEnvironmentService | None = None,
        workspaces: WorkspaceService | None = None,
        leases: WriteScopeLeaseService | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._events = events or EventService(engine)
        self._repository = repository or ExecutionPlanRepository()
        self._environments = environments or ExecutionEnvironmentService(
            engine, events=self._events
        )
        self._workspaces = workspaces or WorkspaceService(engine, events=self._events)
        self._leases = leases or WriteScopeLeaseService(engine, events=self._events)
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

    async def plan(
        self,
        *,
        task: Task,
        route_decision: RouteDecision,
        context_package_id: UUID,
        worker_profile_id: str | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> ExecutionPlan:
        """Chapter 7.1's planner steps, minus workspace allocation (see the
        module docstring's flagged divergence). Provisions a real
        `ExecutionEnvironment` via `ExecutionEnvironmentService.provision`
        under the same transaction, then hashes and persists the plan."""
        if route_decision.task_id != task.task_id:
            raise DdeError(
                "POLICY_DENIED",
                "RouteDecision does not belong to this task",
                details={
                    "task_id": str(task.task_id),
                    "route_decision_task_id": str(route_decision.task_id),
                },
            )
        tenant_id = task.tenant_id
        project_id = task.project_id
        mission_id = task.mission_id
        resolved_worker_profile_id = (
            worker_profile_id or route_decision.selected_worker_profile_id
        )

        async def _op(active: PostgresUnitOfWork) -> ExecutionPlan:
            planned = plan_execution(task=task, route_decision=route_decision)
            resource_limits: dict[str, object] = dict(planned.resource_budget)
            network_policy: dict[str, object] = {
                "mode": "unenforced",
                "reason": (
                    "local_process backend cannot isolate network egress "
                    "(Chapter 7.2 T2 needs container/microVM isolation, "
                    "deferred to DDE-018)"
                ),
            }
            filesystem_policy: dict[str, object] = {
                "workspace_root_only": True,
                "size_cap_mb": DEFAULT_WORKSPACE_SIZE_CAP_MB,
            }
            acquired = await self._environments.acquire(
                tenant_id=tenant_id,
                project_id=project_id,
                environment_class=planned.environment_class,
                resource_limits=resource_limits,
                network_policy=network_policy,
                filesystem_policy=filesystem_policy,
                uow=active,
            )
            environment = acquired.environment
            self._environments.assert_schedulable(environment)

            write_scope_lease_id: UUID | None = None
            if task.expected_write_scope:
                lease = await self._leases.acquire(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission_id=mission_id,
                    task_id=task.task_id,
                    scope_patterns=list(task.expected_write_scope),
                    uow=active,
                )
                write_scope_lease_id = lease.lease_id

            workspace_policy: dict[str, object] = {
                "writable_root": "workspace",
                "size_cap_mb": DEFAULT_WORKSPACE_SIZE_CAP_MB,
            }
            digest = plan_hash(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                task_id=task.task_id,
                route_decision_id=route_decision.decision_id,
                context_package_id=context_package_id,
                worker_profile_id=resolved_worker_profile_id,
                execution_environment_id=environment.environment_id,
                workspace_policy=workspace_policy,
                capability_requirements=planned.capability_requirements,
                enforcement_tier=planned.enforcement_tier,
                autonomy_level=planned.autonomy_level,
                resource_budget=planned.resource_budget,
                time_budget=planned.time_budget,
                token_budget=planned.token_budget,
                network_policy=network_policy,
                filesystem_policy=filesystem_policy,
                checkpoint_policy=planned.checkpoint_policy,
                retry_policy=planned.retry_policy,
                escalation_policy=planned.escalation_policy,
            )
            now = self._clock.now()
            plan_record = ExecutionPlan(
                plan_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                task_id=task.task_id,
                route_decision_id=route_decision.decision_id,
                context_package_id=context_package_id,
                worker_profile_id=resolved_worker_profile_id,
                execution_environment_id=environment.environment_id,
                workspace_policy=workspace_policy,
                capability_requirements=planned.capability_requirements,
                enforcement_tier=planned.enforcement_tier,
                autonomy_level=planned.autonomy_level,
                resource_budget=planned.resource_budget,
                time_budget=planned.time_budget,
                token_budget=planned.token_budget,
                network_policy=network_policy,
                filesystem_policy=filesystem_policy,
                verification_plan_id=None,
                acceptance_oracle_id=None,
                write_scope_lease_id=write_scope_lease_id,
                checkpoint_policy=planned.checkpoint_policy,
                retry_policy=planned.retry_policy,
                escalation_policy=planned.escalation_policy,
                plan_hash=digest,
                status="PLANNED",
                approved_at=None,
                started_at=None,
                ended_at=None,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_plan(active.connection, plan_record)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="ExecutionPlanCommitted",
                aggregate_type="execution_plan",
                aggregate_id=plan_record.plan_id,
                mission_id=mission_id,
                task_id=task.task_id,
                payload={
                    "execution_environment_id": str(environment.environment_id),
                    "enforcement_tier": planned.enforcement_tier,
                    "plan_hash": digest,
                },
                uow=active,
            )
            return plan_record

        return await self._run(uow, tenant_id, project_id, _op)

    async def provision_workspace(
        self,
        *,
        plan: ExecutionPlan,
        task: Task,
        base_revision: str | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> Workspace:
        """Chapter 3.9 step 9 ("Workspace allocated, environment leased"):
        allocates a real `Workspace` bound to `plan.execution_environment_id`
        and `task.task_id`, using `plan.workspace_policy` as Chapter 7.5's
        `create(base_revision, policy)` policy argument."""
        if plan.task_id != task.task_id:
            raise DdeError(
                "POLICY_DENIED",
                "ExecutionPlan does not belong to this task",
                details={
                    "task_id": str(task.task_id),
                    "plan_task_id": str(plan.task_id),
                },
            )
        return await self._workspaces.create(
            tenant_id=plan.tenant_id,
            project_id=plan.project_id,
            mission_id=plan.mission_id,
            task_id=task.task_id,
            execution_environment_id=plan.execution_environment_id,
            base_revision=base_revision,
            policy=plan.workspace_policy,
            uow=uow,
        )

    async def transition(
        self,
        *,
        plan: ExecutionPlan,
        target_status: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> ExecutionPlan:
        """Chapter 3.8: "Definition immutable; status mutable." No
        `lock_version` column exists on `execution_plans` (7.1's field list
        omits one, as does `RouteDecision`'s), so this relies on the
        caller's own already-read `plan.status` plus the state table to
        reject an illegal transition; a true concurrent-writer race is out
        of scope for the same reason it is for `RouteDecision`."""

        async def _op(active: PostgresUnitOfWork) -> ExecutionPlan:
            next_status = transition(
                plan.status, target_status, EXECUTION_PLAN_TRANSITIONS
            )
            now = self._clock.now()
            timestamps: dict[str, object] = {}
            if next_status == "APPROVED":
                timestamps["approved_at"] = now
            elif next_status == "ACTIVE":
                timestamps["started_at"] = now
            elif next_status in {"COMPLETED", "FAILED"}:
                timestamps["ended_at"] = now
            rowcount = await self._repository.update_status(
                active.connection, plan.plan_id, status=next_status, **timestamps
            )
            if rowcount != 1:
                raise DdeError(
                    "POLICY_DENIED",
                    "Unknown execution plan",
                    details={"plan_id": str(plan.plan_id)},
                )
            updated = await self._require_plan(active, plan.plan_id)
            await self._events.append(
                tenant_id=plan.tenant_id,
                project_id=plan.project_id,
                event_type="ExecutionPlanTransitioned",
                aggregate_type="execution_plan",
                aggregate_id=plan.plan_id,
                mission_id=plan.mission_id,
                task_id=plan.task_id,
                payload={"from": plan.status, "to": updated.status},
                uow=active,
            )
            return updated

        return await self._run(uow, plan.tenant_id, plan.project_id, _op)

    async def get_plan(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        plan_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> ExecutionPlan:
        async def _op(active: PostgresUnitOfWork) -> ExecutionPlan:
            return await self._require_plan(active, plan_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def list_for_task(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        task_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[ExecutionPlan]:
        async def _op(active: PostgresUnitOfWork) -> list[ExecutionPlan]:
            return await self._repository.list_for_task(active.connection, task_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def _require_plan(
        self, active: PostgresUnitOfWork, plan_id: UUID
    ) -> ExecutionPlan:
        record = await self._repository.get_plan(active.connection, plan_id)
        if record is None:
            raise DdeError("POLICY_DENIED", "Unknown execution plan")
        return record
