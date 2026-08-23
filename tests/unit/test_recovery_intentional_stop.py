"""PostgreSQL-backed EDR-0010 tests (accepted 2026-08-23).

Production call sites under test:
- `RecoveryService.classify_run_stop_failure_class` -- the classification
  writer the kill-flag refusal sites consult before recording an attempt's
  failure_class;
- `RecoveryService.assert_clear_to_retry` -- refuses any new WorkerRun for
  a task whose latest run holds an ARMED durable stop record, before the
  matrix is even consulted (Chapter 12.4: an intentional stop is never
  blind-retried; only verified absence permits a new mutation).
"""

import platform
import sys
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from engine.capabilities.kill_switch import (
    KILL_FLAG_REASON,
    record_run_stop,
)
from engine.context.repo import repo_root
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.idempotency import CommandLedger
from engine.missions.attempts import TaskAttemptService
from engine.recovery.dispatch import RecoveryService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.worker_fixtures import build_worker_fixture


async def _seed_environment(engine, fixture) -> object:
    """One minimal execution_environments row; worker_runs.environment_id
    carries a real FK to it."""
    now = datetime.now(UTC)
    environment = {
        "environment_id": uuid7(),
        "tenant_id": fixture.tenant.tenant_id,
        "project_id": fixture.tenant.project_id,
        "class": "shared",
        "type": "local_process",
        "os_family": sys.platform,
        "architecture": platform.machine(),
        "runtime_image": "test-image",
        "image_digest": "sha256:test",
        "toolchain_manifest": "{}",
        "toolchain_manifest_hash": "test",
        "resource_limits": "{}",
        "network_policy": "{}",
        "filesystem_policy": "{}",
        "isolation_level": "none",
        "credential_profile_id": None,
        "security_profile_id": None,
        "capability_compatibility": "{}",
        "worker_compatibility": "{}",
        "status": "ACTIVE",
        "health_status": "HEALTHY",
        "lifecycle_state": "ACTIVE",
        "lock_version": 1,
        "created_at": now,
        "updated_at": now,
    }
    columns = ", ".join(environment)
    params = ", ".join(f":{name}" for name in environment)
    statement = text(
        f"INSERT INTO execution_environments ({columns}) VALUES ({params})"  # noqa: S608  code-owned column names, bound values
    )
    async with engine.begin() as connection:
        await connection.execute(statement, environment)
    return environment["environment_id"]


async def _attempt_and_run(fixture, engine) -> tuple[object, object]:
    attempts = TaskAttemptService(engine)
    attempt = await attempts.create(
        task=fixture.task,
        execution_plan=fixture.execution_plan,
        workspace_revision="deadbeef",
        input_context_hash=fixture.context_package.assembly_hash,
    )
    environment_id = await _seed_environment(engine, fixture)
    now = datetime.now(UTC)
    plan_id = fixture.execution_plan.plan_id
    run = {
        "run_id": uuid7(),
        "tenant_id": fixture.tenant.tenant_id,
        "project_id": fixture.tenant.project_id,
        "mission_id": fixture.mission.mission_id,
        "task_attempt_id": attempt.attempt_id,
        "sequence": 1,
        "execution_plan_id": plan_id,
        "worker_id": "worker-test",
        "worker_profile_id": fixture.execution_plan.worker_profile_id,
        "environment_id": environment_id,
        "workspace_id": fixture.workspace.workspace_id,
        "context_package_id": fixture.context_package.package_id,
        "policy_version": "test",
        "lease_set_hash": "test",
        "status": "FAILED",
        "failure_class": None,
        "created_at": now,
        "updated_at": now,
    }
    columns = ", ".join(run)
    params = ", ".join(f":{name}" for name in run)
    statement = text(
        f"INSERT INTO worker_runs ({columns}) VALUES ({params})"  # noqa: S608
    )
    async with engine.begin() as connection:
        await connection.execute(statement, run)
    return attempt, run


@pytest.mark.asyncio
async def test_armed_stop_classifies_intentionally_stopped(tmp_path) -> None:
    """A run whose durable stop record is ARMED classifies as
    INTENTIONALLY_STOPPED; a run with no stop record keeps the borrowed
    legacy AUTHORIZATION_FAILURE meaning."""
    engine = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-EDR10-A"
        )
        workspace = fixture.workspace
        _attempt, run = await _attempt_and_run(fixture, engine)
        service = RecoveryService(engine)

        legacy = await service.classify_run_stop_failure_class(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            worker_run_id=run["run_id"],
        )
        assert legacy == "AUTHORIZATION_FAILURE"

        await record_run_stop(
            CommandLedger(engine),
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            worker_run_id=run["run_id"],
            armed=True,
            reason=KILL_FLAG_REASON,
            uow=None,
        )

        stopped = await service.classify_run_stop_failure_class(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            worker_run_id=run["run_id"],
        )
        assert stopped == "INTENTIONALLY_STOPPED"
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_armed_stop_refuses_new_worker_run_until_disarmed(tmp_path) -> None:
    """assert_clear_to_retry refuses while ARMED (KILL_FLAG_ACTIVE), and a
    DISARMED record -- the operator's acknowledgement flip -- lets the
    guarded path proceed again."""
    engine = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-EDR10-B"
        )
        workspace = fixture.workspace
        attempt, run = await _attempt_and_run(fixture, engine)
        ledger = CommandLedger(engine)
        service = RecoveryService(engine)
        kwargs = {
            "tenant_id": fixture.tenant.tenant_id,
            "project_id": fixture.tenant.project_id,
            "task_id": fixture.task.task_id,
            "mission_id": fixture.mission.mission_id,
        }

        await record_run_stop(
            ledger,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            worker_run_id=run["run_id"],
            armed=True,
            reason=KILL_FLAG_REASON,
            uow=None,
        )
        with pytest.raises(DdeError) as captured:
            await service.assert_clear_to_retry(**kwargs)
        assert captured.value.error_code == "KILL_FLAG_ACTIVE"
        assert captured.value.details is not None
        assert captured.value.details["failure_class"] == "INTENTIONALLY_STOPPED"
        assert captured.value.details["action"] == "acknowledge_stop"

        await TaskAttemptService(engine).fail(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            attempt_id=attempt.attempt_id,
            failure_class="INTENTIONALLY_STOPPED",
            checkpoint_id=None,
        )

        await record_run_stop(
            ledger,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            worker_run_id=run["run_id"],
            armed=False,
            reason="operator acknowledged",
            uow=None,
        )
        retry_of = await service.assert_clear_to_retry(**kwargs)
        assert retry_of == attempt.attempt_id
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()
