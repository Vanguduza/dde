"""Chapter 16.4 control-plane overhead instrumentation.

`record_for_worker_run` is the production mutation that persists one
`ControlPlaneOverheadTask` per `WorkerRun` at the `RUNNING` /
`WorkerRunStarted` site (`WorkerManagerService._drive_lifecycle`). Token
components that have no producer yet (deterministic routing, unimplemented
Route Critic, Stage 1 judge bindings) are stored as honest zeros — they
are counted at this site, not invented elsewhere.

Warm-pool response on environment-provisioning p95 breach is
`ExecutionEnvironmentService.top_up` with a raised target, in a separate
transaction so a pool-maintenance failure cannot roll back the worker run.
Alerts use Chapter 13 attention items (`ApprovalService.raise_attention_item`).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncConnection

from engine.context.repository import (
    ContextCriticFindingRepository,
    ContextRepository,
)
from engine.contracts.control_plane_overhead_task import ControlPlaneOverheadTask
from engine.contracts.execution_plan import ExecutionPlan
from engine.contracts.task import Task
from engine.contracts.tenant_overhead_budget_settings import (
    TenantOverheadBudgetSettings,
)
from engine.contracts.worker_run import WorkerRun
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.environments.service import (
    DEFAULT_WARM_POOL_SIZE,
    ExecutionEnvironmentService,
)
from engine.events.repository import EventsRepository
from engine.governance.service import ApprovalService
from engine.overhead.formula import (
    CONTEXT_CRITIC_INVOCATION_SHARE_ALERT,
    DEFAULT_HARD_CAP_TOKEN_SHARE,
    ENVIRONMENT_PROVISIONING_P95_ALERT_SECONDS,
    OVERHEAD_SECONDS_S_P95_ALERT,
    ROUTE_CRITIC_INVOCATION_SHARE_ALERT,
    TOKEN_SHARE_ALERT,
    TOKEN_SHARE_INVESTIGATE,
    classify_token_share,
    invocation_share,
    overhead_tokens,
    percentile,
    planning_tokens_for,
    token_share,
)
from engine.overhead.repository import ControlPlaneOverheadRepository
from engine.planning.repository import TaskGraphRepository
from engine.routing.repository import RouteDecisionRepository
from engine.truth.db import PostgresUnitOfWork
from engine.workers.usage import ceiling_tokens_from_plan


@dataclass(frozen=True)
class OverheadAlertThresholds:
    token_share_alert: float = TOKEN_SHARE_ALERT
    token_share_investigate: float = TOKEN_SHARE_INVESTIGATE
    overhead_seconds_s_p95_alert: float = OVERHEAD_SECONDS_S_P95_ALERT
    environment_provisioning_p95_alert: float = (
        ENVIRONMENT_PROVISIONING_P95_ALERT_SECONDS
    )
    context_critic_invocation_share_alert: float = CONTEXT_CRITIC_INVOCATION_SHARE_ALERT
    route_critic_invocation_share_alert: float = ROUTE_CRITIC_INVOCATION_SHARE_ALERT


class ControlPlaneOverheadService:
    def __init__(
        self,
        *,
        overhead: ControlPlaneOverheadRepository | None = None,
        contexts: ContextRepository | None = None,
        critic_findings: ContextCriticFindingRepository | None = None,
        events: EventsRepository | None = None,
        routes: RouteDecisionRepository | None = None,
        graphs: TaskGraphRepository | None = None,
        environments: ExecutionEnvironmentService | None = None,
        approvals: ApprovalService | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._overhead = overhead or ControlPlaneOverheadRepository()
        self._contexts = contexts or ContextRepository()
        self._critic_findings = critic_findings or ContextCriticFindingRepository()
        self._events = events or EventsRepository()
        self._routes = routes or RouteDecisionRepository()
        self._graphs = graphs or TaskGraphRepository()
        self._environments = environments
        self._approvals = approvals  # may be None in unit tests
        self._clock = clock or SystemClock()
        self._thresholds = OverheadAlertThresholds()

    async def record_for_worker_run(
        self,
        *,
        uow: PostgresUnitOfWork,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        run: WorkerRun,
        task: Task,
        execution_plan: ExecutionPlan,
    ) -> None:
        active_connection = uow.connection
        package = await self._contexts.get_context_package(
            active_connection, run.context_package_id
        )
        if package is None:
            return

        critic_findings = await self._critic_findings.list_for_package(
            active_connection, run.context_package_id
        )
        context_critic_tokens = sum(f.cost_tokens_estimate for f in critic_findings)
        context_critic_invoked = len(critic_findings) > 0

        now = self._clock.now()
        if run.started_at is None:
            return

        events = await self._events.list_events_for_aggregate(
            active_connection,
            aggregate_type="execution_environment",
            aggregate_id=run.environment_id,
        )

        environment_provisioning_ms = 0
        for evt in reversed(events):
            if evt.event_type != "ExecutionEnvironmentAcquired":
                continue
            raw = evt.payload.get("provisioning_ms")
            if isinstance(raw, int) and raw >= 0:
                environment_provisioning_ms = raw
                break

        queue_wait_seconds = (run.started_at - run.created_at).total_seconds()
        overhead_base_seconds = (run.started_at - package.created_at).total_seconds()
        overhead_seconds_total = overhead_base_seconds + (
            environment_provisioning_ms / 1000.0
        )

        decision = await self._routes.get_route_decision(
            active_connection, execution_plan.route_decision_id
        )
        workload_class = decision.workload_class if decision is not None else "unknown"

        # Deterministic v1 routing (Chapter 6.2) consumes no model tokens.
        # Route Critic (Chapter 6.6) is not implemented — EDR-0005; do not
        # count a hypothetical trigger as an invocation.
        routing_tokens = 0
        route_critic_tokens = 0
        route_critic_invoked = False

        graph = await self._graphs.get_task_graph(active_connection, task.graph_id)
        planning_tokens = 0
        if graph is not None:
            planning_tokens = planning_tokens_for(
                planning_mode=graph.planning_mode,
                texts=(graph.rationale, task.title, task.intent),
            )

        # Judge bindings are rejected by AcceptanceOracleService in Stage 1;
        # judges also run after the worker, so this RUNNING-site write is 0.
        judge_tokens = 0

        tokens = overhead_tokens(
            context_assembly=package.assembly_tokens,
            context_critic=context_critic_tokens,
            routing=routing_tokens,
            route_critic=route_critic_tokens,
            planning=planning_tokens,
            judge=judge_tokens,
        )

        record = ControlPlaneOverheadTask(
            overhead_task_id=run.run_id,
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            task_id=execution_plan.task_id,
            task_attempt_id=run.task_attempt_id,
            worker_run_id=run.run_id,
            execution_plan_id=execution_plan.plan_id,
            context_package_id=run.context_package_id,
            environment_id=run.environment_id,
            estimated_effort=task.estimated_effort,
            context_assembly_tokens=package.assembly_tokens,
            context_critic_tokens=context_critic_tokens,
            routing_tokens=routing_tokens,
            route_critic_tokens=route_critic_tokens,
            planning_tokens=planning_tokens,
            judge_tokens=judge_tokens,
            overhead_tokens=tokens,
            environment_provisioning_ms=environment_provisioning_ms,
            queue_wait_seconds=queue_wait_seconds,
            overhead_seconds_before_first_worker_action_seconds=overhead_seconds_total,
            context_critic_invoked=context_critic_invoked,
            route_critic_invoked=route_critic_invoked,
            workload_class=workload_class,
            created_at=now,
            updated_at=now,
        )

        await self._overhead.insert_overhead_task(active_connection, record)

        if self._approvals is None:
            return

        await self._raise_alerts(
            active_connection=active_connection,
            uow=uow,
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            run=run,
            task=task,
            execution_plan=execution_plan,
            record=record,
        )

    async def _raise_alerts(
        self,
        *,
        active_connection: AsyncConnection,
        uow: PostgresUnitOfWork,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        run: WorkerRun,
        task: Task,
        execution_plan: ExecutionPlan,
        record: ControlPlaneOverheadTask,
    ) -> None:
        approvals = self._approvals
        if approvals is None:
            return

        mission_tokens = ceiling_tokens_from_plan(execution_plan.token_budget) or 0
        settings: (
            TenantOverheadBudgetSettings | None
        ) = await self._overhead.get_tenant_budget_settings(
            active_connection, tenant_id=tenant_id
        )
        hard_cap = (
            float(settings.hard_cap_overhead_token_share)
            if settings is not None
            else DEFAULT_HARD_CAP_TOKEN_SHARE
        )
        share = token_share(record.overhead_tokens, mission_tokens)
        if share is not None:
            kind = classify_token_share(share, hard_cap=hard_cap)
            if kind == "hard_cap":
                await approvals.raise_attention_item(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission_id=mission_id,
                    kind="control_plane_overhead_token_share_hard_cap_exceeded",
                    summary=(
                        f"Control-plane overhead token share {share:.2%} "
                        f"exceeded per-tenant hard cap (>{hard_cap:.2%})."
                    ),
                    uow=uow,
                )
            elif kind == "investigate":
                await approvals.raise_attention_item(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission_id=mission_id,
                    kind="control_plane_overhead_token_share_investigate",
                    summary=(
                        f"Control-plane overhead token share {share:.2%} "
                        f"exceeded investigate threshold "
                        f"(>{self._thresholds.token_share_investigate:.2%})."
                    ),
                    uow=uow,
                )
            elif kind == "alert":
                await approvals.raise_attention_item(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission_id=mission_id,
                    kind="control_plane_overhead_token_share_exceeded",
                    summary=(
                        f"Control-plane overhead token share {share:.2%} "
                        f"exceeded alert threshold "
                        f"(>{self._thresholds.token_share_alert:.2%})."
                    ),
                    uow=uow,
                )

        recent_all = await self._overhead.list_recent_overhead_tasks_all_efforts(
            active_connection,
            tenant_id=tenant_id,
            project_id=project_id,
            limit=200,
        )

        if task.estimated_effort == "s":
            recent_s = await self._overhead.list_recent_overhead_tasks(
                active_connection,
                tenant_id=tenant_id,
                project_id=project_id,
                effort="s",
                limit=200,
            )
            p95_seconds = percentile(
                [
                    float(r.overhead_seconds_before_first_worker_action_seconds)
                    for r in recent_s
                ],
                0.95,
            )
            if (
                p95_seconds is not None
                and p95_seconds > self._thresholds.overhead_seconds_s_p95_alert
            ):
                await approvals.raise_attention_item(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission_id=mission_id,
                    kind="control_plane_overhead_seconds_p95_exceeded",
                    summary=(
                        f"Control-plane overhead seconds p95={p95_seconds:.1f}s "
                        f"exceeded alert threshold "
                        f"(>{self._thresholds.overhead_seconds_s_p95_alert:.0f}s)."
                    ),
                    uow=uow,
                )

        if recent_all:
            p95_env_ms = percentile(
                [float(r.environment_provisioning_ms) for r in recent_all],
                0.95,
            )
            if p95_env_ms is not None:
                p95_env_seconds = p95_env_ms / 1000.0
                if (
                    p95_env_seconds
                    > self._thresholds.environment_provisioning_p95_alert
                ):
                    await approvals.raise_attention_item(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        mission_id=mission_id,
                        kind="control_plane_environment_provisioning_p95_exceeded",
                        summary=(
                            f"Environment provisioning p95={p95_env_seconds:.1f}s "
                            f"exceeded alert threshold "
                            f"(>{self._thresholds.environment_provisioning_p95_alert:.0f}s)."
                        ),
                        uow=uow,
                    )
                    await self._respond_warm_pool(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        environment_id=run.environment_id,
                    )

            ctx_share = invocation_share(
                sum(1 for r in recent_all if r.context_critic_invoked),
                len(recent_all),
            )
            if (
                ctx_share is not None
                and ctx_share > self._thresholds.context_critic_invocation_share_alert
            ):
                await approvals.raise_attention_item(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission_id=mission_id,
                    kind="control_plane_context_critic_invocation_share_exceeded",
                    summary=(
                        f"Context critic invocation share {ctx_share:.1%} "
                        f"exceeded threshold "
                        f"(>{self._thresholds.context_critic_invocation_share_alert:.0%})."
                    ),
                    uow=uow,
                )

            route_share = invocation_share(
                sum(1 for r in recent_all if r.route_critic_invoked),
                len(recent_all),
            )
            if (
                route_share is not None
                and route_share > self._thresholds.route_critic_invocation_share_alert
            ):
                await approvals.raise_attention_item(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission_id=mission_id,
                    kind="control_plane_route_critic_invocation_share_exceeded",
                    summary=(
                        f"Route critic invocation share {route_share:.1%} "
                        f"exceeded threshold "
                        f"(>{self._thresholds.route_critic_invocation_share_alert:.0%})."
                    ),
                    uow=uow,
                )

    async def _respond_warm_pool(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        environment_id: UUID,
    ) -> None:
        """Chapter 16.4: environment provisioning p95 → warm pool sizing
        responds. Best-effort and off the worker transaction: a pool
        failure must not roll back a RUNNING WorkerRun."""
        environments = self._environments
        if environments is None:
            return
        try:
            env = await environments.get_environment(
                tenant_id=tenant_id,
                project_id=project_id,
                environment_id=environment_id,
                uow=None,
            )
            await environments.top_up(
                tenant_id=tenant_id,
                project_id=project_id,
                environment_class=env.class_,
                resource_limits=env.resource_limits,
                network_policy=env.network_policy,
                filesystem_policy=env.filesystem_policy,
                target_size=DEFAULT_WARM_POOL_SIZE + 1,
                uow=None,
            )
        except DdeError:
            return
