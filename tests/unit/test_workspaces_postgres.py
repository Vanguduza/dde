"""PostgreSQL-backed `engine.workspaces`: schema, state-transition,
negative and cleanup tests (Chapter 19.1). Exercises `engine.workspaces.
service.WorkspaceService` — the production writer of `workspaces` (Chapter
3.8) — against a real database, a real git worktree of this repository, and
a real OS subprocess (`LocalProcessBackend`)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import pytest

from engine.capabilities.lease_service import CapabilityLeaseService
from engine.context.repo import repo_root
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.truth.db import open_unit_of_work
from engine.workspaces.repository import WorkspaceRepository
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine, seed_tenant
from tests.support.worker_fixtures import build_worker_fixture


def _list_git_worktrees(root: Path) -> str:
    git_executable = shutil.which("git")
    assert git_executable is not None
    completed = subprocess.run(  # noqa: S603
        [git_executable, "worktree", "list"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


@pytest.mark.asyncio
async def test_schema_round_trip_creates_a_real_git_worktree() -> None:
    """A `workspaces` row read back from the real table validates against
    the JSON-schema-generated contract (Chapter 3.1) — the schema test —
    and its `workspace_path` is a real directory containing a real git
    worktree checked out to a real commit."""
    engine = new_engine()
    root = repo_root()
    service = WorkspaceService(engine, root=root)
    workspace = None
    try:
        tenant = await seed_tenant(engine)
        workspace = await service.create(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            mission_id=None,
            task_id=None,
            execution_environment_id=None,
            base_revision="HEAD",
            policy={"writable_root": "workspace"},
        )

        assert workspace.status == "READY"
        assert workspace.workspace_path is not None
        workspace_path = Path(workspace.workspace_path)
        assert workspace_path.is_dir()
        assert (workspace_path / ".git").exists()
        assert workspace.current_revision == workspace.base_revision
        assert workspace.current_revision is not None
        assert len(workspace.current_revision) == 40  # real full git SHA

        async with open_unit_of_work(
            engine, tenant_id=tenant.tenant_id, project_id=tenant.project_id
        ) as uow:
            reloaded = await WorkspaceRepository().get_workspace(
                uow.connection, workspace.workspace_id
            )
            await uow.commit()
        assert reloaded == workspace
        # `git worktree list` normalises to forward slashes even on Windows.
        assert workspace_path.as_posix() in _list_git_worktrees(root).replace("\\", "/")
    finally:
        if workspace is not None:
            await service.cleanup(workspace=workspace)
        await engine.dispose()


@pytest.mark.asyncio
async def test_execute_runs_a_real_subprocess_and_captures_real_output() -> None:
    """Chapter 7.5's `execute(command)`: a real Python subprocess, run
    inside the real worktree directory, its real stdout/exit code
    captured — not a mock of a worker, an actual OS process."""
    engine = new_engine()
    root = repo_root()
    service = WorkspaceService(engine, root=root)
    workspace = None
    try:
        tenant = await seed_tenant(engine)
        workspace = await service.create(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            mission_id=None,
            task_id=None,
            execution_environment_id=None,
            base_revision="HEAD",
            policy={"writable_root": "workspace"},
        )

        result = await service.execute(
            workspace=workspace,
            command=[sys.executable, "-c", "print('dde-workspace-proof')"],
        )
        assert result.exit_code == 0
        assert "dde-workspace-proof" in result.stdout
        assert result.timed_out is False

        async with open_unit_of_work(
            engine, tenant_id=tenant.tenant_id, project_id=tenant.project_id
        ) as uow:
            reloaded = await WorkspaceRepository().get_workspace(
                uow.connection, workspace.workspace_id
            )
            await uow.commit()
        # execute() transitions READY -> IN_USE -> READY around the run.
        assert reloaded is not None
        assert reloaded.status == "READY"
        assert reloaded.lock_version == workspace.lock_version + 2
    finally:
        if workspace is not None:
            await service.cleanup(workspace=workspace)
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_subprocess_failure_is_captured_not_raised() -> None:
    """Chapter 19.1: "subprocess failure ... is captured as a typed failure
    state, not an unhandled exception." A non-zero exit is data on
    `CommandResult`, never a raised exception."""
    engine = new_engine()
    root = repo_root()
    service = WorkspaceService(engine, root=root)
    workspace = None
    try:
        tenant = await seed_tenant(engine)
        workspace = await service.create(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            mission_id=None,
            task_id=None,
            execution_environment_id=None,
            base_revision="HEAD",
            policy={},
        )

        result = await service.execute(
            workspace=workspace,
            command=[sys.executable, "-c", "import sys; sys.exit(7)"],
        )
        assert result.exit_code == 7
        assert result.timed_out is False
    finally:
        if workspace is not None:
            await service.cleanup(workspace=workspace)
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_bad_base_revision_persists_a_real_failed_row() -> None:
    """Chapter 19.1: "provisioning failure — bad workspace ref". A revision
    that does not resolve to a real commit is caught, persisted as a real
    `FAILED` row, and re-raised as a typed `ENVIRONMENT_FAILED` error."""
    engine = new_engine()
    root = repo_root()
    service = WorkspaceService(engine, root=root)
    try:
        tenant = await seed_tenant(engine)
        with pytest.raises(DdeError) as excinfo:
            await service.create(
                tenant_id=tenant.tenant_id,
                project_id=tenant.project_id,
                mission_id=None,
                task_id=None,
                execution_environment_id=None,
                base_revision="not-a-real-revision-abc123",
                policy={},
            )
        assert excinfo.value.error_code == "ENVIRONMENT_FAILED"
        workspace_id = excinfo.value.details["workspace_id"]

        async with open_unit_of_work(
            engine, tenant_id=tenant.tenant_id, project_id=tenant.project_id
        ) as uow:
            reloaded = await WorkspaceRepository().get_workspace(
                uow.connection, UUID(workspace_id)
            )
            await uow.commit()
        assert reloaded is not None
        assert reloaded.status == "FAILED"
        assert reloaded.workspace_path is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_workspace_escape_and_symlink_escape_are_denied() -> None:
    """Chapter 19.1's "Environment" fixtures: workspace escape, symlink
    escape. `read()`/`write()` reject any path — direct or via a real
    symlink — that resolves outside the workspace root."""
    engine = new_engine()
    root = repo_root()
    service = WorkspaceService(engine, root=root)
    workspace = None
    try:
        tenant = await seed_tenant(engine)
        workspace = await service.create(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            mission_id=None,
            task_id=None,
            execution_environment_id=None,
            base_revision="HEAD",
            policy={},
        )
        assert workspace.workspace_path is not None
        workspace_path = Path(workspace.workspace_path)

        with pytest.raises(DdeError) as escape:
            service.read(workspace, "../outside.txt")
        assert escape.value.error_code == "POLICY_DENIED"

        outside_target = workspace_path.parent / "dde-escape-target.txt"
        outside_target.write_text("secret")
        try:
            symlink_path = workspace_path / "escape-link"
            try:
                symlink_path.symlink_to(outside_target)
            except OSError:
                pytest.skip("symlink creation not permitted in this environment")
            with pytest.raises(DdeError) as symlink_escape:
                service.read(workspace, "escape-link")
            assert symlink_escape.value.error_code == "POLICY_DENIED"
        finally:
            outside_target.unlink(missing_ok=True)

        service.write(workspace, "inside.txt", b"hello")
        assert service.read(workspace, "inside.txt") == b"hello"
    finally:
        if workspace is not None:
            await service.cleanup(workspace=workspace)
        await engine.dispose()


@pytest.mark.asyncio
async def test_cleanup_leaves_no_orphaned_directory_or_worktree() -> None:
    """Explicit cleanup proof required by the mission brief: after
    `cleanup()`, the real directory is gone and `git worktree list` no
    longer references it — no orphan left behind."""
    engine = new_engine()
    root = repo_root()
    service = WorkspaceService(engine, root=root)
    try:
        tenant = await seed_tenant(engine)
        workspace = await service.create(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            mission_id=None,
            task_id=None,
            execution_environment_id=None,
            base_revision="HEAD",
            policy={},
        )
        workspace_path = Path(workspace.workspace_path)  # type: ignore[arg-type]
        assert workspace_path.is_dir()

        cleaned = await service.cleanup(workspace=workspace)

        assert cleaned.status == "CLEANED_UP"
        assert not workspace_path.exists()
        assert str(workspace_path) not in _list_git_worktrees(root)

        # Idempotent: cleaning up an already-cleaned workspace is a no-op.
        again = await service.cleanup(workspace=cleaned)
        assert again.status == "CLEANED_UP"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_capture_revision_and_snapshot_reflect_real_worktree_state(
    tmp_path: Path,
) -> None:
    """Chapter 7.5's `capture_revision()`/`snapshot()`: real `git`
    introspection of the worktree, not a fabricated value.

    DDE-017: `snapshot()` is now gated behind a real, granted
    `capability.git_operations` lease bound to a `worker_run_id` -- granted
    here through the real `CapabilityLeaseService.request()` path, exactly
    as `engine.workers.service.WorkerManagerService.invoke_run` does for a
    real worker run.

    `build_worker_fixture` takes `tmp_path`, not the real `repo_root()`, as
    its own fixture-root argument -- that argument is `tests.support.
    context_fixtures.build_fake_repo`'s isolated stand-in repo for context
    retrieval, entirely separate from the real repository `WorkspaceService`
    itself always operates against (`root`, passed explicitly below).
    Passing the real `repo_root()` there would let `build_fake_repo`
    overwrite real files under it."""
    engine = new_engine()
    root = repo_root()
    service = WorkspaceService(engine, root=root)
    workspace = None
    try:
        fixture = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-WORKSPACE-SNAPSHOT"
        )
        workspace = fixture.workspace
        service.write(workspace, "dde-snapshot-proof.txt", b"proof")

        leases = CapabilityLeaseService(engine)
        worker_run_id = uuid7()
        granted = await leases.request(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.mission.mission_id,
            task_id=fixture.task.task_id,
            execution_plan_id=fixture.execution_plan.plan_id,
            worker_run_id=worker_run_id,
            capability_id="capability.git_operations",
            capability_version="1",
            requested_by="system:test",
            idempotency_key=f"{worker_run_id}:capability.git_operations",
        )
        assert granted.status == "GRANTED"

        snapshot = await service.snapshot(workspace, worker_run_id=worker_run_id)
        assert snapshot["revision"] == workspace.current_revision
        assert "dde-snapshot-proof.txt" in str(snapshot["status_porcelain"])

        recaptured = await service.capture_revision(workspace=workspace)
        assert recaptured.current_revision == workspace.current_revision
    finally:
        if workspace is not None:
            await service.cleanup(workspace=workspace)
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_snapshot_without_a_lease_is_denied(tmp_path: Path) -> None:
    """Chapter 7.2's T1 brokered enforcement, proven directly against
    `WorkspaceService.snapshot()`: no granted `capability.git_operations`
    lease for this `worker_run_id` means the real git subprocess calls
    never run -- fails closed, not silently allowed."""
    engine = new_engine()
    root = repo_root()
    service = WorkspaceService(engine, root=root)
    workspace = None
    try:
        fixture = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-WORKSPACE-SNAPSHOT-DENIED"
        )
        workspace = fixture.workspace

        with pytest.raises(DdeError) as excinfo:
            await service.snapshot(workspace, worker_run_id=uuid7())
        assert excinfo.value.error_code == "POLICY_DENIED"
    finally:
        if workspace is not None:
            await service.cleanup(workspace=workspace)
        await engine.dispose()
