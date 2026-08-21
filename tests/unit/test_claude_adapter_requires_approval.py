"""EDR-0001 Path A -- `adapters/claude/adapter.py`'s mandatory,
non-standing human approval gate (Chapter 13, DDE governance).

Two contract properties are proven here, matching AGENTS.md's Definition
of Done ("Contract test exists and failed before the implementation
existed"):

1. `ClaudeCodeWorkerAdapter.start()` fails closed with `POLICY_DENIED`
   and never spawns a subprocess when no matching `Approval` exists.
2. `external_model_invocation` cannot be satisfied by a `StandingApproval`
   -- neither `grant_standing()` nor `authorize_standing()` can ever mint
   or use one for this approval_type. This is the most important
   regression test: it is what makes "a human manually approve every
   piece of work routed to Claude Code" true structurally, not by
   convention.

A real, injected fake binary (`sys.executable -c <prompt>`) stands in for
the real `claude` CLI -- no real `claude` install is required in CI,
mirroring `ScriptedWorkerAdapter`'s own test pattern of running the current
Python interpreter as a stand-in subprocess.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from adapters.claude.adapter import (
    APPROVAL_TYPE_EXTERNAL_MODEL_INVOCATION,
    WORKER_ID,
    WORKER_PROFILE_ID,
    ClaudeCodeWorkerAdapter,
    ClaudePromptBinding,
    claude_invocation_scope_hash,
)
from engine.context.repo import repo_root
from engine.contracts.worker_run import WorkerRun
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.governance.service import ApprovalService
from engine.governance.types import APPROVAL_TYPES, STANDING_FORBIDDEN_TYPES
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.worker_fixtures import WorkerFixture, build_worker_fixture


def test_external_model_invocation_is_a_declared_approval_type() -> None:
    assert APPROVAL_TYPE_EXTERNAL_MODEL_INVOCATION in APPROVAL_TYPES


def test_external_model_invocation_is_standing_forbidden() -> None:
    """The regression test: proves the literal both modules agree on can
    never be pre-authorised by a `StandingApproval` -- a batch grant
    covering it is structurally impossible, not merely discouraged."""
    assert APPROVAL_TYPE_EXTERNAL_MODEL_INVOCATION in STANDING_FORBIDDEN_TYPES


@pytest.mark.asyncio
async def test_grant_standing_rejects_external_model_invocation() -> None:
    """Real, DB-backed proof (not just frozenset membership): the actual
    production call site a caller would use to pre-authorise a batch of
    Claude Code invocations fails closed."""
    engine = new_engine()
    try:
        service = ApprovalService(engine)
        with pytest.raises(DdeError) as captured:
            await service.grant_standing(
                tenant_id=uuid7(),
                project_id=uuid7(),
                approval_types=[APPROVAL_TYPE_EXTERNAL_MODEL_INVOCATION],
                blast_radius_ceiling="module",
                risk_ceiling="medium",
                cost_ceiling=10.0,
                task_count_ceiling=4,
                path_scope=["engine"],
                forbidden_operations=[],
                valid_from_hours=0,
                valid_until_hours=8,
                granted_by=uuid7(),
                rationale="attempted overnight Claude Code batch",
                idempotency_key=f"standing-claude-{uuid7().hex[:12]}",
            )
        assert captured.value.error_code == "POLICY_DENIED"
    finally:
        await engine.dispose()


@dataclass
class _PreparedCase:
    adapter: ClaudeCodeWorkerAdapter
    worker_run: WorkerRun
    approvals: ApprovalService
    scope_hash: str
    fixture: WorkerFixture


async def _prepared_case(
    engine: AsyncEngine,
    tmp_path: Path,
    mission_slug: str,
    *,
    prompt: str,
) -> _PreparedCase:
    """Shared setup: a real, persisted Mission/Task/ExecutionPlan/Workspace
    (`tests.support.worker_fixtures.build_worker_fixture`), a bound
    fake-binary prompt, and a `prepare()`d adapter -- everything `start()`
    needs except the approval decision itself, which each test supplies
    (or withholds) independently."""
    fixture = await build_worker_fixture(engine, tmp_path, mission_slug=mission_slug)
    workspaces = WorkspaceService(engine, root=repo_root())
    approvals = ApprovalService(engine)
    adapter = ClaudeCodeWorkerAdapter(workspaces, approvals)

    binding = ClaudePromptBinding(
        prompt=prompt,
        binary=sys.executable,
        args=("-c",),
    )
    adapter.bind_prompt(fixture.execution_plan.plan_id, binding)
    await adapter.prepare(
        execution_plan=fixture.execution_plan,
        context_ref=uuid7(),
        env_ref=fixture.workspace,
    )

    now = datetime.now(UTC)
    worker_run = WorkerRun(
        run_id=uuid7(),
        tenant_id=fixture.tenant.tenant_id,
        project_id=fixture.tenant.project_id,
        mission_id=fixture.mission.mission_id,
        task_attempt_id=uuid7(),
        sequence=1,
        execution_plan_id=fixture.execution_plan.plan_id,
        worker_id=WORKER_ID,
        worker_profile_id=WORKER_PROFILE_ID,
        environment_id=fixture.execution_plan.execution_environment_id,
        workspace_id=fixture.workspace.workspace_id,
        context_package_id=fixture.execution_plan.context_package_id,
        policy_version="test-policy-v1",
        lease_set_hash="deadbeef",
        status="STARTING",
        created_at=now,
        updated_at=now,
    )
    scope_hash = claude_invocation_scope_hash(
        mission_id=worker_run.mission_id,
        execution_plan_id=worker_run.execution_plan_id,
        binding=binding,
    )
    return _PreparedCase(
        adapter=adapter,
        worker_run=worker_run,
        approvals=approvals,
        scope_hash=scope_hash,
        fixture=fixture,
    )


@pytest.mark.asyncio
async def test_start_fails_closed_without_an_approved_approval(
    tmp_path: Path,
) -> None:
    db_engine = new_engine()
    case: _PreparedCase | None = None
    try:
        case = await _prepared_case(
            db_engine,
            tmp_path,
            f"MISSION-CLAUDE-DENY-{uuid7().hex[:8]}",
            prompt="print('should never run')",
        )
        with pytest.raises(DdeError) as captured:
            await case.adapter.start(case.worker_run)
        assert captured.value.error_code == "POLICY_DENIED"
        # No subprocess ran: no RunHandle was ever recorded for this run.
        status = await case.adapter.status(case.worker_run)
        assert status.state == "PENDING"
    finally:
        if case is not None:
            await WorkspaceService(db_engine, root=repo_root()).cleanup(
                workspace=case.fixture.workspace
            )
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_start_succeeds_once_a_matching_approval_is_decided(
    tmp_path: Path,
) -> None:
    db_engine = new_engine()
    case: _PreparedCase | None = None
    try:
        case = await _prepared_case(
            db_engine,
            tmp_path,
            f"MISSION-CLAUDE-APPROVE-{uuid7().hex[:8]}",
            prompt="print('dde-claude-run-proof')",
        )
        requested = await case.approvals.request(
            tenant_id=case.worker_run.tenant_id,
            project_id=case.worker_run.project_id,
            mission_id=case.worker_run.mission_id,
            approval_type=APPROVAL_TYPE_EXTERNAL_MODEL_INVOCATION,
            scope_hash=case.scope_hash,
            requested_by=uuid7(),
            idempotency_key=f"claude-approval-{uuid7().hex[:12]}",
        )
        await case.approvals.decide(
            tenant_id=case.worker_run.tenant_id,
            project_id=case.worker_run.project_id,
            approval_id=requested.approval_id,
            decision="APPROVED",
            decided_by=uuid7(),
            rationale="human reviewed the exact prompt before approving",
            scope_hash=case.scope_hash,
        )

        handle = await case.adapter.start(case.worker_run)

        assert handle.exit_code == 0
        assert "dde-claude-run-proof" in handle.stdout
        assert not handle.timed_out

        status = await case.adapter.status(case.worker_run)
        assert status.state == "COMPLETED"

        usage = await case.adapter.collect_usage(case.worker_run)
        assert usage.cost_usd == 0.0
    finally:
        if case is not None:
            await WorkspaceService(db_engine, root=repo_root()).cleanup(
                workspace=case.fixture.workspace
            )
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_approval_for_a_different_prompt_does_not_authorise_this_one(
    tmp_path: Path,
) -> None:
    """A re-planned prompt is a materially different plan (Chapter 13.1) --
    an approval decided for one prompt must never authorise a different
    one, even under the same mission/execution_plan."""
    db_engine = new_engine()
    case: _PreparedCase | None = None
    try:
        case = await _prepared_case(
            db_engine,
            tmp_path,
            f"MISSION-CLAUDE-MISMATCH-{uuid7().hex[:8]}",
            prompt="print('the approved prompt')",
        )
        other_binding = ClaudePromptBinding(
            prompt="print('a different, unapproved prompt')",
            binary=sys.executable,
            args=("-c",),
        )
        unrelated_scope_hash = claude_invocation_scope_hash(
            mission_id=case.worker_run.mission_id,
            execution_plan_id=case.worker_run.execution_plan_id,
            binding=other_binding,
        )
        requested = await case.approvals.request(
            tenant_id=case.worker_run.tenant_id,
            project_id=case.worker_run.project_id,
            mission_id=case.worker_run.mission_id,
            approval_type=APPROVAL_TYPE_EXTERNAL_MODEL_INVOCATION,
            scope_hash=unrelated_scope_hash,
            requested_by=uuid7(),
            idempotency_key=f"claude-approval-mismatch-{uuid7().hex[:12]}",
        )
        await case.approvals.decide(
            tenant_id=case.worker_run.tenant_id,
            project_id=case.worker_run.project_id,
            approval_id=requested.approval_id,
            decision="APPROVED",
            decided_by=uuid7(),
            rationale="approved the wrong prompt",
            scope_hash=unrelated_scope_hash,
        )

        with pytest.raises(DdeError) as captured:
            await case.adapter.start(case.worker_run)
        assert captured.value.error_code == "POLICY_DENIED"
    finally:
        if case is not None:
            await WorkspaceService(db_engine, root=repo_root()).cleanup(
                workspace=case.fixture.workspace
            )
        await db_engine.dispose()
