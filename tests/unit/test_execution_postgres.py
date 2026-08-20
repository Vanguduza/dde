"""PostgreSQL-backed `engine.execution`: schema, state-transition and
negative tests (Chapter 19.1), and the mission's full acceptance proof —
`ExecutionPlanService.plan()` against a real, persisted `RouteDecision` and
`Task`, provisioning a real `ExecutionEnvironment`, allocating a real
`Workspace` (git worktree), running a real command in it, and tearing both
down."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from engine.context.repo import repo_root
from engine.core.errors import DdeError
from engine.environments.service import ExecutionEnvironmentService
from engine.execution.hashing import plan_hash
from engine.execution.repository import ExecutionPlanRepository
from engine.execution.service import ExecutionPlanService
from engine.truth.db import open_unit_of_work
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.execution_fixtures import build_execution_fixture


@pytest.mark.asyncio
async def test_schema_round_trip_and_acceptance_full_lifecycle(tmp_path: Path) -> None:
    """The mission's acceptance proof, end to end: a real `RouteDecision`
    and `Task` (Chapter 3.9 step 6) produce a real `ExecutionPlan` (step 7)
    bound to a real, provisioned `ExecutionEnvironment`; a real `Workspace`
    (step 9) is allocated from it, a real command runs inside it with
    captured output, and both are torn down with observable lifecycle
    transitions."""
    root = repo_root()
    db_engine = new_engine()
    plan_service = ExecutionPlanService(db_engine)
    workspace = None
    try:
        fixture = await build_execution_fixture(
            db_engine, tmp_path, mission_slug="MISSION-EXEC-SCHEMA"
        )

        plan = await plan_service.plan(
            task=fixture.task,
            route_decision=fixture.route_decision,
            context_package_id=fixture.context_package.package_id,
        )

        assert plan.status == "PLANNED"
        assert plan.route_decision_id == fixture.route_decision.decision_id
        assert plan.task_id == fixture.task.task_id
        assert (
            plan.worker_profile_id == fixture.route_decision.selected_worker_profile_id
        )
        assert plan.enforcement_tier == "audit_only"
        assert (
            plan.capability_requirements == fixture.route_decision.required_capabilities
        )
        assert plan.resource_budget["cpu_seconds"] > 0
        assert plan.plan_hash

        environments = ExecutionEnvironmentService(db_engine)
        environment = await environments.get_environment(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            environment_id=plan.execution_environment_id,
        )
        assert environment.lifecycle_state == "READY"
        assert environment.type == "local"

        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            reloaded_plan = await ExecutionPlanRepository().get_plan(
                uow.connection, plan.plan_id
            )
            await uow.commit()
        assert reloaded_plan == plan

        # Chapter 3.9 step 9: workspace allocated, environment leased.
        workspace = await plan_service.provision_workspace(
            plan=plan, task=fixture.task, base_revision="HEAD"
        )
        assert workspace.status == "READY"
        assert workspace.execution_environment_id == plan.execution_environment_id
        assert workspace.task_id == fixture.task.task_id

        workspaces = WorkspaceService(db_engine, root=root)
        result = await workspaces.execute(
            workspace=workspace,
            command=[sys.executable, "-c", "print('dde-execution-plan-proof')"],
        )
        assert result.exit_code == 0
        assert "dde-execution-plan-proof" in result.stdout

        active_plan = await plan_service.transition(plan=plan, target_status="APPROVED")
        active_plan = await plan_service.transition(
            plan=active_plan, target_status="ACTIVE"
        )
        assert active_plan.started_at is not None

        # Teardown: real environment drain/retire, real workspace cleanup.
        active_env = await environments.transition(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            environment_id=environment.environment_id,
            target_lifecycle_state="ACTIVE",
            lock_version=environment.lock_version,
        )
        draining_env = await environments.transition(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            environment_id=environment.environment_id,
            target_lifecycle_state="DRAINING",
            lock_version=active_env.lock_version,
        )
        retired_env = await environments.transition(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            environment_id=environment.environment_id,
            target_lifecycle_state="RETIRED",
            lock_version=draining_env.lock_version,
        )
        assert retired_env.lifecycle_state == "RETIRED"

        assert workspace.workspace_path is not None
        workspace_path = Path(workspace.workspace_path)
        cleaned_workspace = await workspaces.cleanup(workspace=workspace)
        assert cleaned_workspace.status == "CLEANED_UP"
        assert not workspace_path.exists()

        completed_plan = await plan_service.transition(
            plan=active_plan, target_status="COMPLETED"
        )
        assert completed_plan.status == "COMPLETED"
        assert completed_plan.ended_at is not None
        workspace = None
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(workspace=workspace)
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_two_different_efforts_produce_two_different_budgets_and_hashes(
    tmp_path: Path,
) -> None:
    """Chapter 7.1's "compute budgets" step is real and input-dependent: two
    tasks with different `estimated_effort` get two different, concrete
    `resource_budget`/`time_budget`/`token_budget` values and two different
    `plan_hash`es — not one hardcoded plan reused for every task."""
    db_engine = new_engine()
    plan_service = ExecutionPlanService(db_engine)
    try:
        small = await build_execution_fixture(
            db_engine,
            tmp_path,
            mission_slug="MISSION-EXEC-SMALL",
            estimated_effort_override="xs",
        )
        large = await build_execution_fixture(
            db_engine,
            tmp_path,
            mission_slug="MISSION-EXEC-LARGE",
            estimated_effort_override="l",
        )

        small_plan = await plan_service.plan(
            task=small.task,
            route_decision=small.route_decision,
            context_package_id=small.context_package.package_id,
        )
        large_plan = await plan_service.plan(
            task=large.task,
            route_decision=large.route_decision,
            context_package_id=large.context_package.package_id,
        )

        assert (
            small_plan.resource_budget["cpu_seconds"]
            < large_plan.resource_budget["cpu_seconds"]
        )
        assert (
            small_plan.token_budget["max_tokens"]
            < large_plan.token_budget["max_tokens"]
        )
        assert small_plan.plan_hash != large_plan.plan_hash
    finally:
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_negative_route_decision_task_mismatch_is_rejected(
    tmp_path: Path,
) -> None:
    """A `RouteDecision` for a different `task_id` is a policy violation,
    not silently accepted (`ExecutionPlan` must reference upstream data
    that genuinely belongs to the task being planned)."""
    db_engine = new_engine()
    plan_service = ExecutionPlanService(db_engine)
    try:
        first = await build_execution_fixture(
            db_engine, tmp_path, mission_slug="MISSION-EXEC-MISMATCH-A"
        )
        second = await build_execution_fixture(
            db_engine, tmp_path, mission_slug="MISSION-EXEC-MISMATCH-B"
        )

        with pytest.raises(DdeError) as excinfo:
            await plan_service.plan(
                task=first.task,
                route_decision=second.route_decision,
                context_package_id=first.context_package.package_id,
            )
        assert excinfo.value.error_code == "POLICY_DENIED"
    finally:
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_negative_illegal_status_transition_is_rejected(tmp_path: Path) -> None:
    """State-transition negative case: `PLANNED -> COMPLETED` skips
    `APPROVED`/`ACTIVE` and must be rejected, not silently allowed."""
    db_engine = new_engine()
    plan_service = ExecutionPlanService(db_engine)
    try:
        fixture = await build_execution_fixture(
            db_engine, tmp_path, mission_slug="MISSION-EXEC-ILLEGAL"
        )
        plan = await plan_service.plan(
            task=fixture.task,
            route_decision=fixture.route_decision,
            context_package_id=fixture.context_package.package_id,
        )
        with pytest.raises(DdeError) as excinfo:
            await plan_service.transition(plan=plan, target_status="COMPLETED")
        assert excinfo.value.error_code == "VERSION_CONFLICT"
    finally:
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_plan_hash_is_deterministic_and_excludes_lifecycle_columns(
    tmp_path: Path,
) -> None:
    """Chapter 3.10: the hash covers definition fields only, so recomputing
    it from a persisted plan's own fields reproduces the stored value."""
    db_engine = new_engine()
    plan_service = ExecutionPlanService(db_engine)
    try:
        fixture = await build_execution_fixture(
            db_engine, tmp_path, mission_slug="MISSION-EXEC-HASH"
        )
        plan = await plan_service.plan(
            task=fixture.task,
            route_decision=fixture.route_decision,
            context_package_id=fixture.context_package.package_id,
        )
        recomputed = plan_hash(
            tenant_id=plan.tenant_id,
            project_id=plan.project_id,
            mission_id=plan.mission_id,
            task_id=plan.task_id,
            route_decision_id=plan.route_decision_id,
            context_package_id=plan.context_package_id,
            worker_profile_id=plan.worker_profile_id,
            execution_environment_id=plan.execution_environment_id,
            workspace_policy=plan.workspace_policy,
            capability_requirements=plan.capability_requirements,
            enforcement_tier=plan.enforcement_tier,
            autonomy_level=plan.autonomy_level,
            resource_budget=plan.resource_budget,
            time_budget=plan.time_budget,
            token_budget=plan.token_budget,
            network_policy=plan.network_policy,
            filesystem_policy=plan.filesystem_policy,
            checkpoint_policy=plan.checkpoint_policy,
            retry_policy=plan.retry_policy,
            escalation_policy=plan.escalation_policy,
        )
        assert recomputed == plan.plan_hash
    finally:
        await db_engine.dispose()
