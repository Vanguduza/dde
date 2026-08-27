"""PostgreSQL-backed Chapter 12.3 / 4.6 (DDE-024).

Production call sites: WorkerManagerService.invoke_run consults the matrix
before a new WorkerRun; RecoveryService.replan supersedes the graph without
releasing write-scope leases; AUTHORIZATION_FAILURE cannot be bypassed by a
new idempotency key.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from engine.capabilities.lease_service import CapabilityLeaseService
from engine.context.repo import repo_root
from engine.core.clock import SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.integration.service import WriteScopeLeaseService
from engine.missions.attempts import TaskAttemptService
from engine.missions.service import MissionService
from engine.planning.planner import PLANNER_POLICY_VERSION
from engine.planning.service import TaskGraphService
from engine.planning.templates import add_endpoint_template
from engine.recovery.dispatch import RecoveryService
from engine.workers.adapter import WorkerAction
from engine.workers.registry import WorkerProfileRegistry
from engine.workers.scripted_adapter import ScriptedWorkerAdapter
from engine.workers.service import WorkerManagerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine, seed_tenant
from tests.support.worker_fixtures import build_worker_fixture
from tests.unit.test_planning_postgres import REQUIREMENT_SLUG, _create_mission


async def _manager(engine, workspaces: WorkspaceService) -> WorkerManagerService:
    leases = CapabilityLeaseService(engine)
    registry = WorkerProfileRegistry()
    await registry.register_profile(ScriptedWorkerAdapter(workspaces, leases))
    return WorkerManagerService(engine, registry, leases=leases)


@pytest.mark.asyncio
async def test_authorization_failure_cannot_be_retried_with_a_new_key(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-RECOVERY-AUTH"
        )
        workspace = fixture.workspace
        attempts = TaskAttemptService(engine)
        first = await attempts.create(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace_revision="deadbeef",
            input_context_hash=fixture.context_package.assembly_hash,
        )
        await attempts.fail(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            attempt_id=first.attempt_id,
            failure_class="AUTHORIZATION_FAILURE",
            checkpoint_id=None,
        )
        workspaces = WorkspaceService(engine, root=repo_root())
        manager = await _manager(engine, workspaces)
        with pytest.raises(DdeError) as captured:
            await manager.invoke_run(
                task=fixture.task,
                execution_plan=fixture.execution_plan,
                workspace=fixture.workspace,
                input_context_hash=fixture.context_package.assembly_hash,
                action=WorkerAction(command=[sys.executable, "-c", "pass"]),
                idempotency_key="recovery-auth-2",
            )
        assert captured.value.error_code == "POLICY_DENIED"
        assert captured.value.details is not None
        assert captured.value.details["failure_class"] == "AUTHORIZATION_FAILURE"
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_second_worker_failure_reroutes_instead_of_another_run(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-RECOVERY-WORKER"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(engine, root=repo_root())
        manager = await _manager(engine, workspaces)
        fail_action = WorkerAction(
            command=[sys.executable, "-c", "raise SystemExit(1)"]
        )
        first = await manager.invoke_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=fail_action,
            idempotency_key="recovery-worker-1",
        )
        assert first.status == "FAILED"
        second = await manager.resume_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=fail_action,
            attempt_id=first.task_attempt_id,
            idempotency_key="recovery-worker-2",
        )
        assert second.status == "FAILED"
        assert second.task_attempt_id == first.task_attempt_id
        with pytest.raises(DdeError) as captured:
            await manager.invoke_run(
                task=fixture.task,
                execution_plan=fixture.execution_plan,
                workspace=fixture.workspace,
                input_context_hash=fixture.context_package.assembly_hash,
                action=WorkerAction(command=[sys.executable, "-c", "pass"]),
                idempotency_key="recovery-worker-3",
            )
        assert captured.value.details is not None
        assert captured.value.details["action"] == "reroute"
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_replan_supersedes_graph_and_keeps_write_scope_lease() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        events = EventService(engine)
        graphs = TaskGraphService(engine)
        missions = MissionService(engine, events, task_graphs=graphs)
        mission = await _create_mission(
            missions, fixture, slug="MISSION-RECOVERY-REPLAN"
        )
        graph_id = uuid7()
        planned = add_endpoint_template(mission, graph_id, SystemClock())
        graph = await missions.create_task_graph(
            mission=mission,
            graph_id=graph_id,
            tasks=planned.tasks,
            edges=planned.edges,
            planning_mode="template",
            planner_policy_version=PLANNER_POLICY_VERSION,
            rationale=planned.rationale,
            created_by_principal=fixture.principal_id,
            approved_requirement_slugs={REQUIREMENT_SLUG},
        )
        active = await graphs.activate_task_graph(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            graph_id=graph_id,
            lock_version=graph.lock_version,
        )
        lead = planned.tasks[0]
        lease = await WriteScopeLeaseService(engine).acquire(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=mission.mission_id,
            task_id=lead.task_id,
            scope_patterns=list(lead.expected_write_scope),
            exclusive=True,
        )
        recovery = RecoveryService(
            engine, events=events, missions=missions, graphs=graphs
        )
        decision, new_graph = await recovery.replan(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=mission.mission_id,
            graph_id=active.graph_id,
            trigger="SPECIFICATION_FAILURE",
            created_by_principal=fixture.principal_id,
            approved_requirement_slugs={REQUIREMENT_SLUG},
            idempotency_key="recovery-replan-1",
        )
        assert new_graph.status == "ACTIVE"
        assert new_graph.supersedes_id == active.graph_id
        prior = await graphs.get_task_graph(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            graph_id=active.graph_id,
        )
        assert prior.status == "SUPERSEDED"
        assert "SUPERSEDE" in decision.dispositions.values()
        held = await WriteScopeLeaseService(engine).list_held_for_task(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            task_id=lead.task_id,
        )
        assert [item.lease_id for item in held] == [lease.lease_id]
        replayed, again = await recovery.replan(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=mission.mission_id,
            graph_id=active.graph_id,
            trigger="SPECIFICATION_FAILURE",
            created_by_principal=fixture.principal_id,
            approved_requirement_slugs={REQUIREMENT_SLUG},
            idempotency_key="recovery-replan-1",
        )
        assert again.graph_id == new_graph.graph_id
        assert replayed.trigger == decision.trigger
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_superseded_task_cannot_start_a_new_worker_run(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-RECOVERY-SUPERSEDE"
        )
        workspace = fixture.workspace
        events = EventService(engine)
        missions = MissionService(engine, events)
        current = await missions.get_task(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            task_id=fixture.task.task_id,
        )
        await missions.transition_task(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            task_id=fixture.task.task_id,
            target_status="SUPERSEDED",
            lock_version=current.lock_version,
        )
        workspaces = WorkspaceService(engine, root=repo_root())
        manager = await _manager(engine, workspaces)
        with pytest.raises(DdeError) as captured:
            await manager.invoke_run(
                task=fixture.task,
                execution_plan=fixture.execution_plan,
                workspace=fixture.workspace,
                input_context_hash=fixture.context_package.assembly_hash,
                action=WorkerAction(command=[sys.executable, "-c", "pass"]),
                idempotency_key="recovery-supersede-1",
            )
        assert captured.value.error_code == "POLICY_DENIED"
        assert captured.value.details is not None
        assert captured.value.details["status"] == "SUPERSEDED"
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()
