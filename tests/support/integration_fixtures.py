"""Shared PostgreSQL fixtures for `engine.integration` tests (Chapter 19.1).

`advance_task_to_verified` builds on `tests.support.execution_fixtures.
build_execution_fixture`'s pattern one step further than `tests.support.
worker_fixtures`/`verification_fixtures` already go: a real, provisioned
`Workspace`, a real `COMPLETED` `WorkerRun` that wrote caller-supplied
files, a real (by default `PASSED`) `VerificationRun` against a caller-
supplied `CheckSpec`, and the real `WriteScopeLease` `engine.execution.
service.ExecutionPlanService.plan()` now acquires -- everything DDE-013's
merge queue depends on, produced through real services rather than
hand-inserted rows. Every task built here is `task_class="verification"`
so it always routes to `profile.deterministic_runner`, the one real,
certified `WorkerAdapter` Stage 1 has (`tests/support/worker_fixtures.py`'s
same deliberate choice) -- a `Task`'s `expected_write_scope` is not
restricted to implementing task classes, only *required non-empty* for
them (`engine/planning/validate.py`), so it is still set explicitly here.

`build_shared_mission_tasks` mirrors `tests.support.routing_fixtures.
build_routing_fixture`'s pattern, doubled into *one* mission: two
`task_class="verification"` nodes sharing one declared write scope, each
trivially a valid graph terminal on its own (`is_verifier`), so a real
merge-queue conflict test can integrate one task, then rebase the other's
real diff onto the first's real, mission-branch-advancing commit -- the
exact "two tasks touching the same shared path, scheduled sequentially"
case Chapter 10.3 itself names.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.capabilities.lease_service import CapabilityLeaseService
from engine.context.model import ContextBudgetExceeded
from engine.context.service import ContextService
from engine.contracts.context_package import ContextPackage
from engine.contracts.execution_plan import ExecutionPlan
from engine.contracts.mission import Mission
from engine.contracts.route_decision import RouteDecision
from engine.contracts.task import Task
from engine.contracts.verification_run import VerificationRun
from engine.contracts.workspace import Workspace
from engine.contracts.write_scope_lease import WriteScopeLease
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.execution.service import ExecutionPlanService
from engine.integration.service import WriteScopeLeaseService
from engine.missions.service import MissionService
from engine.planning.planner import PLANNER_POLICY_VERSION
from engine.routing.service import RouterService
from engine.truth.service import TruthService
from engine.verification.checks import CheckSpec
from engine.verification.oracle import AcceptanceOracleService
from engine.verification.runner import VerificationRunnerService
from engine.workers.adapter import WorkerAction
from engine.workers.registry import WorkerProfileRegistry
from engine.workers.scripted_adapter import ScriptedWorkerAdapter
from engine.workers.service import WorkerManagerService
from engine.workspaces.service import WorkspaceService
from tests.support.capability_fixtures import ensure_capabilities_seeded
from tests.support.context_fixtures import build_fake_repo
from tests.support.db import TenantFixture, seed_tenant


@dataclass
class AdvancedTask:
    """A real, verified attempt at one task -- everything
    `IntegrationQueueService.submit()` depends on."""

    task: Task
    execution_plan: ExecutionPlan
    workspace: Workspace
    lease: WriteScopeLease
    verification_run: VerificationRun
    task_attempt_id: UUID


async def advance_task_to_verified(
    engine: AsyncEngine,
    root: Path,
    *,
    tenant: TenantFixture,
    task: Task,
    context_package: ContextPackage,
    route_decision: RouteDecision,
    write_files: dict[str, bytes],
    idempotency_prefix: str,
    base_revision: str = "HEAD",
    check_command: list[str] | None = None,
    expect_verification_status: str = "PASSED",
) -> AdvancedTask:
    await ensure_capabilities_seeded(
        engine, tenant_id=tenant.tenant_id, project_id=tenant.project_id
    )
    plan_service = ExecutionPlanService(engine)
    plan = await plan_service.plan(
        task=task,
        route_decision=route_decision,
        context_package_id=context_package.package_id,
    )
    assert plan.write_scope_lease_id is not None, plan
    workspace = await plan_service.provision_workspace(
        plan=plan, task=task, base_revision=base_revision
    )

    workspaces = WorkspaceService(engine, root=root)
    leases = CapabilityLeaseService(engine)
    registry = WorkerProfileRegistry()
    await registry.register_profile(ScriptedWorkerAdapter(workspaces, leases))
    manager = WorkerManagerService(engine, registry, leases=leases)
    action = WorkerAction(
        command=(sys.executable, "-c", "pass"), write_files=write_files
    )
    worker_run = await manager.invoke_run(
        task=task,
        execution_plan=plan,
        workspace=workspace,
        input_context_hash=context_package.assembly_hash,
        action=action,
        idempotency_key=f"{idempotency_prefix}-worker-run",
    )
    assert worker_run.status == "COMPLETED", worker_run

    command = check_command or [sys.executable, "-c", "import sys; sys.exit(0)"]
    oracle_service = AcceptanceOracleService(engine)
    oracle = await oracle_service.define(
        task=task,
        outcomes=[
            CheckSpec(
                outcome_id=uuid7(),
                statement="a trivial, deterministic check",
                kind="test",
                ref="trivial:check",
                command=command,
            )
        ],
    )
    runner = VerificationRunnerService(engine, workspaces)
    verification_run = await runner.run(
        task=task,
        worker_run=worker_run,
        workspace=workspace,
        oracle=oracle,
        idempotency_key=f"{idempotency_prefix}-verification-run",
    )
    assert verification_run.status == expect_verification_status, verification_run

    lease_service = WriteScopeLeaseService(engine)
    lease = await lease_service.get_lease(
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        lease_id=plan.write_scope_lease_id,
    )

    return AdvancedTask(
        task=task,
        execution_plan=plan,
        workspace=workspace,
        lease=lease,
        verification_run=verification_run,
        task_attempt_id=worker_run.task_attempt_id,
    )


@dataclass
class SharedMissionFixture:
    tenant: TenantFixture
    mission: Mission
    task_a: Task
    context_a: ContextPackage
    route_decision_a: RouteDecision
    task_b: Task
    context_b: ContextPackage
    route_decision_b: RouteDecision


async def build_shared_mission_tasks(
    engine: AsyncEngine,
    root: Path,
    *,
    mission_slug: str,
    scope: list[str],
) -> SharedMissionFixture:
    """Two `verification` tasks in one mission, both declaring the same
    `scope` -- a real stand-in for Chapter 10.3's `serialised_paths` case,
    where two tasks legitimately touch the same shared path but only ever
    hold their (identical) exclusive lease one at a time."""
    build_fake_repo(root)
    tenant = await seed_tenant(engine)
    requirement_slug = f"REQ-{mission_slug}"
    truth = TruthService(engine)
    requirement = await truth.draft_requirement(
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        slug=requirement_slug,
        statement="Integration fixture tasks integrate through a real merge queue",
        constraints=[],
        acceptance_conditions=[
            "Both tasks' diffs land through IntegrationQueueService"
        ],
    )
    await truth.approve_requirement(
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        requirement_id=requirement.requirement_id,
    )

    mission_service = MissionService(engine, EventService(engine))
    mission = await mission_service.create_mission(
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        slug=mission_slug,
        title="Integration fixture mission",
        intent="Exercise the real merge queue end to end",
        success_definition="Both tasks' proposals resolve through the merge queue",
        scope=["engine", "tests"],
        requirement_refs=[requirement_slug],
        autonomy_ceiling=3,
    )

    now = datetime.now(UTC)
    graph_id = uuid7()
    task_a_id = uuid7()
    task_b_id = uuid7()

    def _task(task_id: UUID, title: str) -> Task:
        # `task_class="verification"`: trivially a valid terminal on its own
        # (`is_verifier` in `validate_graph`), and the only class the real
        # router sends to `profile.deterministic_runner`.
        return Task(
            task_id=task_id,
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            mission_id=mission.mission_id,
            graph_id=graph_id,
            title=title,
            intent=f"Exercise the merge queue for {title}",
            task_class="verification",
            requirement_refs=[requirement_slug],
            feature_refs=[],
            success_criteria=["Behaviour is verified"],
            expected_write_scope=scope,
            expected_read_scope=scope,
            blast_radius="local",
            risk_class="low",
            estimated_effort="xs",
            autonomy_ceiling=2,
            requires_approval=False,
            verification_profile_ref="unit",
            status="CREATED",
            lock_version=1,
            created_at=now,
            updated_at=now,
        )

    task_a = _task(task_a_id, "Task A under test")
    task_b = _task(task_b_id, "Task B under test")
    graph = await mission_service.create_task_graph(
        mission=mission,
        graph_id=graph_id,
        tasks=[task_a, task_b],
        edges=[],
        planning_mode="template",
        planner_policy_version=PLANNER_POLICY_VERSION,
        rationale="DDE-013 integration fixture",
        created_by_principal=tenant.principal_id,
        approved_requirement_slugs={requirement_slug},
    )
    assert graph.status == "APPROVED", graph

    persisted = await mission_service.list_tasks_for_graph(
        tenant_id=tenant.tenant_id, project_id=tenant.project_id, graph_id=graph_id
    )
    by_id = {item.task_id: item for item in persisted}

    context_service = ContextService(engine, root=root)
    context_a = await context_service.compile(task=by_id[task_a_id])
    assert not isinstance(context_a, ContextBudgetExceeded), context_a
    context_b = await context_service.compile(task=by_id[task_b_id])
    assert not isinstance(context_b, ContextBudgetExceeded), context_b

    router = RouterService(engine)
    route_decision_a = await router.route(task=by_id[task_a_id])
    route_decision_b = await router.route(task=by_id[task_b_id])

    return SharedMissionFixture(
        tenant=tenant,
        mission=mission,
        task_a=by_id[task_a_id],
        context_a=context_a,
        route_decision_a=route_decision_a,
        task_b=by_id[task_b_id],
        context_b=context_b,
        route_decision_b=route_decision_b,
    )
