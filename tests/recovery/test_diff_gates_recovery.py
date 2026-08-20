"""`engine.integration` diff-gate durability (Chapter 19.1): a fresh
session/engine reads back the exact committed `DiffGateReport` the writing
process produced on a real `IntegrationQueueService.integrate` call.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.context.repo import repo_root
from engine.integration import git
from engine.integration.gate_service import DiffGateService
from engine.integration.service import IntegrationQueueService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.execution_fixtures import build_execution_fixture
from tests.support.integration_fixtures import advance_task_to_verified


@pytest.mark.asyncio
async def test_second_session_sees_the_exact_committed_gate_report(
    tmp_path: Path,
) -> None:
    root = repo_root()
    writer_engine = new_engine()
    workspace = None
    task_branch = None
    mission_branch = None
    tenant_id = None
    project_id = None
    report_id = None
    committed = None
    try:
        fixture = await build_execution_fixture(
            writer_engine,
            tmp_path,
            mission_slug="MISSION-GATE-RECOVERY",
            task_class="verification",
        )
        advanced = await advance_task_to_verified(
            writer_engine,
            tmp_path,
            tenant=fixture.tenant,
            task=fixture.task,
            context_package=fixture.context_package,
            route_decision=fixture.route_decision,
            write_files={
                "engine/routing/dde021-recovery.txt": b"gate recovery proof\n"
            },
            idempotency_prefix="dde021-recovery",
        )
        workspace = advanced.workspace
        task_branch = f"task/{advanced.task.task_id}-a"
        mission_branch = f"mission/{advanced.task.mission_id}"
        tenant_id = advanced.task.tenant_id
        project_id = advanced.task.project_id
        queue = IntegrationQueueService(writer_engine, root=root)
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
        merged = await queue.integrate(proposal=proposal, workspace=advanced.workspace)
        assert merged.status == "MERGED"
        writer_gates = DiffGateService(writer_engine)
        reports = await writer_gates.list_for_proposal(
            tenant_id=tenant_id,
            project_id=project_id,
            proposal_id=proposal.proposal_id,
        )
        assert len(reports) == 1
        committed = reports[0]
        report_id = committed.report_id
    finally:
        await writer_engine.dispose()

    reader_engine = new_engine()
    try:
        reader = DiffGateService(reader_engine)
        assert (
            tenant_id is not None and project_id is not None and report_id is not None
        )
        reloaded = await reader.get_report(
            tenant_id=tenant_id,
            project_id=project_id,
            report_id=report_id,
        )
        assert reloaded == committed
        assert reader.verify_sbom(reloaded) is True
    finally:
        if workspace is not None:
            await WorkspaceService(reader_engine, root=root).cleanup(
                workspace=workspace
            )
        if task_branch is not None:
            git.delete_branch(root, task_branch)
        if mission_branch is not None:
            git.delete_branch(root, mission_branch)
        await reader_engine.dispose()
