"""Chapter 7.2's T1 "brokered" enforcement, proven directly at the two real
Stage 1 call sites DDE-017 wires it into: `ScriptedWorkerAdapter.start()`
(`capability.run_local_process`/`capability.workspace_filesystem`) and
`WorkspaceService.snapshot()` (`capability.git_operations`, exercised via
the adapter's own write-file path). `tests/unit/
test_capability_leases_postgres.py` covers the same lifecycle at the
`CapabilityLeaseService` level in isolation; this file proves the guard is
actually wired into the real side-effecting call sites, not merely
implemented and unused.

A `WorkerRun` used here is a real, in-memory Pydantic value fabricated from
a real, planned `ExecutionPlan` -- deliberately not persisted through
`WorkerManagerService.invoke_run()` (which auto-requests/grants leases for
every action, see that module's docstring), so a "no lease exists yet"
starting point is directly reachable rather than something that has to be
routed around.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from engine.capabilities.lease_service import CapabilityLeaseService
from engine.context.repo import repo_root
from engine.contracts.worker_run import WorkerRun
from engine.core.clock import SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.execution.service import ExecutionPlanService
from engine.workers.adapter import WorkerAction
from engine.workers.scripted_adapter import ScriptedWorkerAdapter
from engine.workspaces.service import WorkspaceService
from tests.support.capability_fixtures import ensure_capabilities_seeded
from tests.support.db import new_engine
from tests.support.execution_fixtures import build_execution_fixture


async def _planned_workspace(engine, tmp_path: Path, *, mission_slug: str):
    execution_fixture = await build_execution_fixture(
        engine, tmp_path, mission_slug=mission_slug, task_class="verification"
    )
    await ensure_capabilities_seeded(
        engine,
        tenant_id=execution_fixture.tenant.tenant_id,
        project_id=execution_fixture.tenant.project_id,
    )
    plan_service = ExecutionPlanService(engine)
    plan = await plan_service.plan(
        task=execution_fixture.task,
        route_decision=execution_fixture.route_decision,
        context_package_id=execution_fixture.context_package.package_id,
    )
    workspace = await plan_service.provision_workspace(
        plan=plan, task=execution_fixture.task, base_revision="HEAD"
    )
    return execution_fixture, plan, workspace


def _fabricate_worker_run(execution_fixture, plan, workspace) -> WorkerRun:
    now = SystemClock().now()
    return WorkerRun(
        run_id=uuid7(),
        tenant_id=execution_fixture.tenant.tenant_id,
        project_id=execution_fixture.tenant.project_id,
        mission_id=execution_fixture.mission.mission_id,
        task_attempt_id=uuid7(),
        sequence=1,
        execution_plan_id=plan.plan_id,
        worker_id="worker.scripted-deterministic-v1",
        worker_profile_id="profile.deterministic_runner",
        environment_id=plan.execution_environment_id,
        workspace_id=workspace.workspace_id,
        context_package_id=plan.context_package_id,
        policy_version="test",
        lease_set_hash="test",
        status="RUNNING",
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_negative_start_without_a_lease_is_denied(tmp_path: Path) -> None:
    """The real acceptance case: a worker run attempted without ANY
    granted `CapabilityLease` for `capability.run_local_process` is
    rejected before the real subprocess ever spawns -- fails closed, not
    silently allowed."""
    root = repo_root()
    engine = new_engine()
    workspace = None
    try:
        fixture, plan, workspace = await _planned_workspace(
            engine, tmp_path, mission_slug="MISSION-GATE-DENY"
        )
        workspaces = WorkspaceService(engine, root=root)
        leases = CapabilityLeaseService(engine)
        adapter = ScriptedWorkerAdapter(workspaces, leases)
        action = WorkerAction(
            command=[sys.executable, "-c", "print('must-not-run')"]
        )
        adapter.bind_action(plan.plan_id, action)
        await adapter.prepare(
            execution_plan=plan, context_ref=plan.context_package_id, env_ref=workspace
        )
        run = _fabricate_worker_run(fixture, plan, workspace)

        with pytest.raises(DdeError) as excinfo:
            await adapter.start(run)
        assert excinfo.value.error_code == "POLICY_DENIED"
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=root).cleanup(workspace=workspace)
        await engine.dispose()


@pytest.mark.asyncio
async def test_positive_start_with_a_granted_lease_proceeds_unchanged(
    tmp_path: Path,
) -> None:
    """Once every capability the action needs has a real, granted lease,
    `start()` behaves exactly as it did before this mission (no regression
    to DDE-011's real subprocess execution, file writes or git snapshot)."""
    root = repo_root()
    engine = new_engine()
    workspace = None
    try:
        fixture, plan, workspace = await _planned_workspace(
            engine, tmp_path, mission_slug="MISSION-GATE-ALLOW"
        )
        workspaces = WorkspaceService(engine, root=root)
        leases = CapabilityLeaseService(engine)
        adapter = ScriptedWorkerAdapter(workspaces, leases)
        action = WorkerAction(
            command=[sys.executable, "-c", "print('dde-gate-allow-proof')"],
            write_files={"dde-gate-allow.txt": b"proof\n"},
        )
        adapter.bind_action(plan.plan_id, action)
        await adapter.prepare(
            execution_plan=plan, context_ref=plan.context_package_id, env_ref=workspace
        )
        run = _fabricate_worker_run(fixture, plan, workspace)

        for capability_id in (
            "capability.workspace_filesystem",
            "capability.git_operations",
            "capability.run_local_process",
        ):
            granted = await leases.request(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                mission_id=fixture.mission.mission_id,
                task_id=fixture.task.task_id,
                execution_plan_id=plan.plan_id,
                worker_run_id=run.run_id,
                capability_id=capability_id,
                capability_version="1",
                requested_by="system:test",
                idempotency_key=f"{run.run_id}:{capability_id}",
            )
            assert granted.status == "GRANTED"

        handle = await adapter.start(run)
        assert handle.exit_code == 0
        assert "dde-gate-allow-proof" in handle.stdout
        assert "dde-gate-allow.txt" in handle.changed_files
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=root).cleanup(workspace=workspace)
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_snapshot_without_a_lease_is_denied_end_to_end(
    tmp_path: Path,
) -> None:
    """`capability.git_operations` gated independently of
    `capability.workspace_filesystem`: granting the write lease but not
    the git one still fails closed before the git subprocess runs."""
    root = repo_root()
    engine = new_engine()
    workspace = None
    try:
        fixture, plan, workspace = await _planned_workspace(
            engine, tmp_path, mission_slug="MISSION-GATE-PARTIAL"
        )
        workspaces = WorkspaceService(engine, root=root)
        leases = CapabilityLeaseService(engine)
        adapter = ScriptedWorkerAdapter(workspaces, leases)
        action = WorkerAction(
            command=[sys.executable, "-c", "print('must-not-run')"],
            write_files={"dde-gate-partial.txt": b"proof\n"},
        )
        adapter.bind_action(plan.plan_id, action)
        await adapter.prepare(
            execution_plan=plan, context_ref=plan.context_package_id, env_ref=workspace
        )
        run = _fabricate_worker_run(fixture, plan, workspace)

        await leases.request(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.mission.mission_id,
            task_id=fixture.task.task_id,
            execution_plan_id=plan.plan_id,
            worker_run_id=run.run_id,
            capability_id="capability.workspace_filesystem",
            capability_version="1",
            requested_by="system:test",
            idempotency_key=f"{run.run_id}:capability.workspace_filesystem",
        )

        with pytest.raises(DdeError) as excinfo:
            await adapter.start(run)
        assert excinfo.value.error_code == "POLICY_DENIED"
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=root).cleanup(workspace=workspace)
        await engine.dispose()


@pytest.mark.asyncio
async def test_revoked_mid_run_denies_the_next_gated_call_in_the_same_run(
    tmp_path: Path,
) -> None:
    """AGENTS.md/Chapter 18.2's S2 exit-gate scenario, proven against the
    real `ScriptedWorkerAdapter`: a lease revoked concurrently with a real,
    long-ish `start()` invocation is still held for that in-flight call
    (Stage 1 has no T2 containment to interrupt an already-running
    subprocess), but the SECOND, separate `start()` call in the same run
    is denied -- the real, achievable "mid-run revocation" granularity."""
    root = repo_root()
    engine = new_engine()
    workspace = None
    try:
        fixture, plan, workspace = await _planned_workspace(
            engine, tmp_path, mission_slug="MISSION-GATE-REVOKE-MIDRUN"
        )
        workspaces = WorkspaceService(engine, root=root)
        leases = CapabilityLeaseService(engine)
        adapter = ScriptedWorkerAdapter(workspaces, leases)
        # A real, measurably slow command -- long enough for a concurrent
        # revocation to race its completion.
        action = WorkerAction(
            command=[
                sys.executable,
                "-c",
                "import time; time.sleep(0.2); print('slow-op-done')",
            ]
        )
        adapter.bind_action(plan.plan_id, action)
        await adapter.prepare(
            execution_plan=plan, context_ref=plan.context_package_id, env_ref=workspace
        )
        run = _fabricate_worker_run(fixture, plan, workspace)

        granted = await leases.request(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.mission.mission_id,
            task_id=fixture.task.task_id,
            execution_plan_id=plan.plan_id,
            worker_run_id=run.run_id,
            capability_id="capability.run_local_process",
            capability_version="1",
            requested_by="system:test",
            idempotency_key=f"{run.run_id}:capability.run_local_process",
        )
        assert granted.status == "GRANTED"

        async def revoke_while_running() -> None:
            await asyncio.sleep(0.05)
            await leases.revoke(lease=granted, reason="operator revoked mid-run")

        handle, _ = await asyncio.gather(adapter.start(run), revoke_while_running())
        assert handle.exit_code == 0
        assert "slow-op-done" in handle.stdout

        # The lease is now durably REVOKED; the NEXT gated call in this
        # same run -- a second, separate start() -- fails closed.
        with pytest.raises(DdeError) as excinfo:
            await adapter.start(run)
        assert excinfo.value.error_code == "POLICY_DENIED"
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=root).cleanup(workspace=workspace)
        await engine.dispose()
