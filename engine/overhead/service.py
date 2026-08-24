"""Chapter 16.4 control-plane overhead instrumentation.

This service computes real overhead measurements derived from production
call sites and persists them durably.
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
from engine.events.repository import EventsRepository
from engine.governance.service import ApprovalService
from engine.overhead.repository import ControlPlaneOverheadRepository
from engine.truth.db import PostgresUnitOfWork
from engine.workers.usage import ceiling_tokens_from_plan


@dataclass(frozen=True)
class OverheadAlertThresholds:
    token_share_alert: float = 0.25
    token_share_investigate: float = 0.35
    overhead_seconds_s_p95_alert: float = 90.0
    environment_provisioning_p95_alert: float = 45.0
    context_critic_invocation_share_alert: float = 0.30


class ControlPlaneOverheadService:
    def __init__(
        self,
        *,
        overhead: ControlPlaneOverheadRepository | None = None,
        contexts: ContextRepository | None = None,
        critic_findings: ContextCriticFindingRepository | None = None,
        events: EventsRepository | None = None,
        approvals: ApprovalService | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._overhead = overhead or ControlPlaneOverheadRepository()
        self._contexts = contexts or ContextRepository()
        self._critic_findings = critic_findings or ContextCriticFindingRepository()
        self._events = events or EventsRepository()
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

        # Durable telemetry is "real production measurements":
        # - environment provisioning from ExecutionEnvironmentAcquired/SlowProvision
        # - overhead seconds from context package creation to worker "RUNNING"
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

        overhead_tokens = package.assembly_tokens + context_critic_tokens

        record = ControlPlaneOverheadTask(
            overhead_task_id=run.run_id,  # deterministic 1:1 for now
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
            overhead_tokens=overhead_tokens,
            environment_provisioning_ms=environment_provisioning_ms,
            queue_wait_seconds=queue_wait_seconds,
            overhead_seconds_before_first_worker_action_seconds=overhead_seconds_total,
            context_critic_invoked=context_critic_invoked,
            created_at=now,
            updated_at=now,
        )

        await self._overhead.insert_overhead_task(active_connection, record)

        # Attention/alert wiring (Chapter 13) — reuse existing machinery.
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
            else 0.40
        )
        token_share_alert = self._thresholds.token_share_alert
        token_share_investigate = self._thresholds.token_share_investigate
        overhead_seconds_threshold = self._thresholds.overhead_seconds_s_p95_alert
        environment_provisioning_threshold = (
            self._thresholds.environment_provisioning_p95_alert
        )
        context_critic_share_threshold = (
            self._thresholds.context_critic_invocation_share_alert
        )
        if mission_tokens > 0:
            token_share = record.overhead_tokens / float(mission_tokens)
            if token_share > hard_cap:
                await approvals.raise_attention_item(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission_id=mission_id,
                    kind="control_plane_overhead_token_share_hard_cap_exceeded",
                    summary=(
                        f"Control-plane overhead token share {token_share:.2%} "
                        f"exceeded per-tenant hard cap (>{hard_cap:.2%})."
                    ),
                    uow=uow,
                )
            elif token_share > token_share_investigate:
                await approvals.raise_attention_item(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission_id=mission_id,
                    kind="control_plane_overhead_token_share_investigate",
                    summary=(
                        f"Control-plane overhead token share {token_share:.2%} "
                        f"exceeded investigate threshold "
                        f"(>{token_share_investigate:.2%})."
                    ),
                    uow=uow,
                )
            elif token_share > token_share_alert:
                await approvals.raise_attention_item(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission_id=mission_id,
                    kind="control_plane_overhead_token_share_exceeded",
                    summary=(
                        f"Control-plane overhead token share {token_share:.2%} "
                        f"exceeded alert threshold "
                        f"(>{token_share_alert:.2%})."
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
            if recent_s:
                recent_seconds = sorted(
                    r.overhead_seconds_before_first_worker_action_seconds
                    for r in recent_s
                )
                p95_index = int(0.95 * (len(recent_seconds) - 1))
                p95_seconds = recent_seconds[p95_index]
                if p95_seconds > overhead_seconds_threshold:
                    await approvals.raise_attention_item(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        mission_id=mission_id,
                        kind="control_plane_overhead_seconds_p95_exceeded",
                        summary=(
                            f"Control-plane overhead seconds p95={p95_seconds:.1f}s "
                            f"exceeded alert threshold "
                            f"(>{overhead_seconds_threshold:.0f}s)."
                        ),
                        uow=uow,
                    )

        if recent_all:
            recent_env = sorted(r.environment_provisioning_ms for r in recent_all)
            p95_env_idx = int(0.95 * (len(recent_env) - 1))
            p95_env_ms = recent_env[p95_env_idx]
            p95_env_seconds = p95_env_ms / 1000.0
            if p95_env_seconds > environment_provisioning_threshold:
                await approvals.raise_attention_item(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission_id=mission_id,
                    kind="control_plane_environment_provisioning_p95_exceeded",
                    summary=(
                        f"Environment provisioning p95={p95_env_seconds:.1f}s "
                        f"exceeded alert threshold "
                        f"(>{environment_provisioning_threshold:.0f}s)."
                    ),
                    uow=uow,
                )

            ctx_invocations = sum(1 for r in recent_all if r.context_critic_invoked)
            critic_share = ctx_invocations / float(len(recent_all))
            if critic_share > context_critic_share_threshold:
                await approvals.raise_attention_item(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission_id=mission_id,
                    kind="control_plane_context_critic_invocation_share_exceeded",
                    summary=(
                        f"Context critic invocation share {critic_share:.1%} "
                        f"exceeded threshold "
                        f"(>{context_critic_share_threshold:.0%})."
                    ),
                    uow=uow,
                )
