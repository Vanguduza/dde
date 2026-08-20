"""PostgreSQL-backed `IntegrationProposal` merge queue: schema,
state-transition, negative and recovery tests (Chapter 19.1). Exercises
`engine.integration.service.IntegrationQueueService` -- the production
writer of `integration_proposals` (Chapter 3.8) -- against a real
database, real git worktrees of this repository, and real `git rebase`
conflicts (Chapter 10.4/10.5)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from engine.context.repo import repo_root
from engine.integration import git
from engine.integration.service import IntegrationQueueService, WriteScopeLeaseService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.execution_fixtures import build_execution_fixture
from tests.support.integration_fixtures import (
    advance_task_to_verified,
    build_shared_mission_tasks,
)


def _show_blob(root: Path, revision: str, path: str) -> str:
    """A real read of one file's real content at one real commit -- proof
    of "real git history", not an assertion about this test's own state."""
    git_executable = shutil.which("git")
    assert git_executable is not None
    completed = subprocess.run(  # noqa: S603
        [git_executable, "show", f"{revision}:{path}"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


@pytest.mark.asyncio
async def test_successful_integration_fast_forwards_the_mission_branch(
    tmp_path: Path,
) -> None:
    """Chapter 10.4's happy path end to end: a `QUEUED` proposal backed by
    a real `PASSED` `VerificationRun` reaches `MERGED`, and the mission
    integration branch's real `HEAD` is the proposal's real, committed
    revision -- provable by reading the real file content back out of git
    history, not by trusting the row."""
    engine = new_engine()
    root = repo_root()
    workspace = None
    mission_branch = None
    task_branch = None
    try:
        fixture = await build_execution_fixture(
            engine,
            tmp_path,
            mission_slug="MISSION-QUEUE-HAPPY",
            task_class="verification",
        )
        advanced = await advance_task_to_verified(
            engine,
            tmp_path,
            tenant=fixture.tenant,
            task=fixture.task,
            context_package=fixture.context_package,
            route_decision=fixture.route_decision,
            write_files={
                "engine/routing/dde013-happy-path.txt": b"integration proof\n"
            },
            idempotency_prefix="dde013-queue-happy",
        )
        workspace = advanced.workspace
        task_branch = f"task/{advanced.task.task_id}-a"
        mission_branch = f"mission/{advanced.task.mission_id}"

        queue = IntegrationQueueService(engine, root=root)
        proposal = await queue.submit(
            tenant_id=advanced.task.tenant_id,
            project_id=advanced.task.project_id,
            mission_id=advanced.task.mission_id,
            task_id=advanced.task.task_id,
            task_attempt_id=advanced.task_attempt_id,
            workspace=advanced.workspace,
            lease=advanced.lease,
            verification_run_id=advanced.verification_run.verification_run_id,
            attempt_label="a",
        )
        assert proposal.status == "QUEUED"
        assert proposal.source_branch == task_branch
        assert "engine/routing/dde013-happy-path.txt" in proposal.changed_paths

        reloaded = await queue.get_proposal(
            tenant_id=advanced.task.tenant_id,
            project_id=advanced.task.project_id,
            proposal_id=proposal.proposal_id,
        )
        assert reloaded == proposal  # schema round trip

        merged = await queue.integrate(proposal=proposal, workspace=advanced.workspace)
        assert merged.status == "MERGED"
        assert merged.conflict_class is None

        real_head = git.rev_parse(root, mission_branch)
        assert real_head == merged.proposed_revision
        content = _show_blob(root, real_head, "engine/routing/dde013-happy-path.txt")
        assert content == "integration proof\n"

        # Idempotent: calling integrate() again on an already-terminal
        # proposal just returns its current state, it does not re-run.
        again = await queue.integrate(proposal=merged, workspace=advanced.workspace)
        assert again == merged
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=root).cleanup(workspace=workspace)
        if task_branch is not None:
            git.delete_branch(root, task_branch)
        if mission_branch is not None:
            git.delete_branch(root, mission_branch)
        await engine.dispose()


@pytest.mark.asyncio
async def test_diff_reaching_outside_the_lease_scope_is_rejected(
    tmp_path: Path,
) -> None:
    """Chapter 10.3/10.4's mandatory scope gate: a real changed path outside
    the `WriteScopeLease`'s declared patterns is a real `REJECTED`
    proposal, never a silent merge."""
    engine = new_engine()
    root = repo_root()
    workspace = None
    mission_branch = None
    task_branch = None
    try:
        fixture = await build_execution_fixture(
            engine,
            tmp_path,
            mission_slug="MISSION-QUEUE-SCOPE",
            task_class="verification",
        )
        assert fixture.task.expected_write_scope == ["engine/routing"]
        advanced = await advance_task_to_verified(
            engine,
            tmp_path,
            tenant=fixture.tenant,
            task=fixture.task,
            context_package=fixture.context_package,
            route_decision=fixture.route_decision,
            write_files={
                "docs/dde013-scope-violation.txt": b"outside declared scope\n"
            },
            idempotency_prefix="dde013-queue-scope",
        )
        workspace = advanced.workspace
        task_branch = f"task/{advanced.task.task_id}-a"
        mission_branch = f"mission/{advanced.task.mission_id}"

        queue = IntegrationQueueService(engine, root=root)
        proposal = await queue.submit(
            tenant_id=advanced.task.tenant_id,
            project_id=advanced.task.project_id,
            mission_id=advanced.task.mission_id,
            task_id=advanced.task.task_id,
            task_attempt_id=advanced.task_attempt_id,
            workspace=advanced.workspace,
            lease=advanced.lease,
            verification_run_id=advanced.verification_run.verification_run_id,
            attempt_label="a",
        )
        rejected = await queue.integrate(
            proposal=proposal, workspace=advanced.workspace
        )
        assert rejected.status == "REJECTED"
        assert rejected.conflict_class == "scope_violation"
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=root).cleanup(workspace=workspace)
        if task_branch is not None:
            git.delete_branch(root, task_branch)
        if mission_branch is not None:
            git.delete_branch(root, mission_branch)
        await engine.dispose()


@pytest.mark.asyncio
async def test_integration_gates_on_a_real_passed_verification_run(
    tmp_path: Path,
) -> None:
    """The mission's explicit acceptance criterion: the merge queue gates
    on the real DDE-012 `VerificationRun.status` field, not a fabricated
    readiness signal. A real `FAILED` run (a real non-zero exit) refuses
    integration."""
    engine = new_engine()
    root = repo_root()
    workspace = None
    mission_branch = None
    task_branch = None
    try:
        fixture = await build_execution_fixture(
            engine,
            tmp_path,
            mission_slug="MISSION-QUEUE-GATE",
            task_class="verification",
        )
        advanced = await advance_task_to_verified(
            engine,
            tmp_path,
            tenant=fixture.tenant,
            task=fixture.task,
            context_package=fixture.context_package,
            route_decision=fixture.route_decision,
            write_files={"engine/routing/dde013-gate.txt": b"gate check\n"},
            idempotency_prefix="dde013-queue-gate",
            check_command=[sys.executable, "-c", "import sys; sys.exit(1)"],
            expect_verification_status="FAILED",
        )
        workspace = advanced.workspace
        task_branch = f"task/{advanced.task.task_id}-a"
        mission_branch = f"mission/{advanced.task.mission_id}"

        queue = IntegrationQueueService(engine, root=root)
        proposal = await queue.submit(
            tenant_id=advanced.task.tenant_id,
            project_id=advanced.task.project_id,
            mission_id=advanced.task.mission_id,
            task_id=advanced.task.task_id,
            task_attempt_id=advanced.task_attempt_id,
            workspace=advanced.workspace,
            lease=advanced.lease,
            verification_run_id=advanced.verification_run.verification_run_id,
            attempt_label="a",
        )
        rejected = await queue.integrate(
            proposal=proposal, workspace=advanced.workspace
        )
        assert rejected.status == "REJECTED"

        real_head = git.rev_parse(root, mission_branch)
        # The mission branch was bootstrapped at the proposal's base
        # revision but never fast-forwarded past it -- a rejected gate
        # must never advance the mainline.
        assert real_head == proposal.base_revision
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=root).cleanup(workspace=workspace)
        if task_branch is not None:
            git.delete_branch(root, task_branch)
        if mission_branch is not None:
            git.delete_branch(root, mission_branch)
        await engine.dispose()


@pytest.mark.asyncio
async def test_real_rebase_conflict_is_detected_as_a_conflict_state(
    tmp_path: Path,
) -> None:
    """Chapter 10.3's `serialised_paths` case, exercised for real: task A's
    diff integrates first and advances the real mission branch; task B's
    workspace, branched from the same original base revision *before*
    that advance, touches the identical line of the identical file with
    different content. Chapter 10.4's real `git rebase` genuinely
    conflicts -- detected and persisted as `CONFLICT(textual)`, never an
    unhandled exception, and the mission branch is left exactly where task
    A's merge left it."""
    engine = new_engine()
    root = repo_root()
    workspace_a = None
    workspace_b = None
    mission_branch = None
    task_branch_a = None
    task_branch_b = None
    candidate_path = "tests/fixtures/dde013-rebase-conflict/shared.txt"
    try:
        shared = await build_shared_mission_tasks(
            engine,
            tmp_path,
            mission_slug="MISSION-QUEUE-CONFLICT",
            scope=["tests/fixtures/dde013-rebase-conflict"],
        )
        queue = IntegrationQueueService(engine, root=root)

        advanced_a = await advance_task_to_verified(
            engine,
            tmp_path,
            tenant=shared.tenant,
            task=shared.task_a,
            context_package=shared.context_a,
            route_decision=shared.route_decision_a,
            write_files={candidate_path: b"line written by task A\n"},
            idempotency_prefix="dde013-conflict-a",
        )
        workspace_a = advanced_a.workspace
        task_branch_a = f"task/{advanced_a.task.task_id}-a"
        mission_branch = f"mission/{shared.mission.mission_id}"

        proposal_a = await queue.submit(
            tenant_id=advanced_a.task.tenant_id,
            project_id=advanced_a.task.project_id,
            mission_id=advanced_a.task.mission_id,
            task_id=advanced_a.task.task_id,
            task_attempt_id=advanced_a.task_attempt_id,
            workspace=advanced_a.workspace,
            lease=advanced_a.lease,
            verification_run_id=advanced_a.verification_run.verification_run_id,
            attempt_label="a",
        )
        merged_a = await queue.integrate(
            proposal=proposal_a, workspace=advanced_a.workspace
        )
        assert merged_a.status == "MERGED", merged_a

        lease_service = WriteScopeLeaseService(engine)
        released_a = await lease_service.release(lease=advanced_a.lease)
        assert released_a.status == "RELEASED"

        advanced_b = await advance_task_to_verified(
            engine,
            tmp_path,
            tenant=shared.tenant,
            task=shared.task_b,
            context_package=shared.context_b,
            route_decision=shared.route_decision_b,
            write_files={candidate_path: b"a different line written by task B\n"},
            idempotency_prefix="dde013-conflict-b",
        )
        workspace_b = advanced_b.workspace
        task_branch_b = f"task/{advanced_b.task.task_id}-a"

        proposal_b = await queue.submit(
            tenant_id=advanced_b.task.tenant_id,
            project_id=advanced_b.task.project_id,
            mission_id=advanced_b.task.mission_id,
            task_id=advanced_b.task.task_id,
            task_attempt_id=advanced_b.task_attempt_id,
            workspace=advanced_b.workspace,
            lease=advanced_b.lease,
            verification_run_id=advanced_b.verification_run.verification_run_id,
            attempt_label="a",
        )
        # Both workspaces were provisioned from the real, shared "HEAD" --
        # task B's proposal still names that same original base revision,
        # while the mission branch has already moved past it via task A.
        assert proposal_b.base_revision == proposal_a.base_revision
        assert proposal_b.base_revision != merged_a.proposed_revision

        conflicted = await queue.integrate(
            proposal=proposal_b, workspace=advanced_b.workspace
        )
        assert conflicted.status == "CONFLICT"
        assert conflicted.conflict_class == "textual"

        # The mission branch must be left exactly where task A's real
        # merge left it -- a detected conflict never partially advances it.
        real_head = git.rev_parse(root, mission_branch)
        assert real_head == merged_a.proposed_revision

        # The worktree itself must be left clean -- `rebase --abort` really
        # ran, not a mid-conflict working tree.
        assert advanced_b.workspace.workspace_path is not None
        assert git.status_porcelain(Path(advanced_b.workspace.workspace_path)) == ""
    finally:
        if workspace_a is not None:
            await WorkspaceService(engine, root=root).cleanup(workspace=workspace_a)
        if workspace_b is not None:
            await WorkspaceService(engine, root=root).cleanup(workspace=workspace_b)
        if task_branch_a is not None:
            git.delete_branch(root, task_branch_a)
        if task_branch_b is not None:
            git.delete_branch(root, task_branch_b)
        if mission_branch is not None:
            git.delete_branch(root, mission_branch)
        await engine.dispose()
