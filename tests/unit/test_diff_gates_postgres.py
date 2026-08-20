"""PostgreSQL-backed Chapter 9.6–9.7 diff gates: schema, state-transition,
negative and wiring tests (Chapter 19.1). Exercises `DiffGateService`
through the real `IntegrationQueueService.integrate` path -- Chapter 10.4
step 3 -- not a parallel unused helper.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.context.repo import repo_root
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.integration import git
from engine.integration.gate_service import DiffGateService
from engine.integration.service import IntegrationQueueService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.execution_fixtures import build_execution_fixture
from tests.support.integration_fixtures import advance_task_to_verified

PLANTED_SECRET = "-----BEGIN RSA PRIVATE KEY-----"  # noqa: S105


async def _submit_and_integrate(
    engine,
    tmp_path: Path,
    *,
    mission_slug: str,
    write_files: dict[str, bytes],
    idempotency_prefix: str,
):
    root = repo_root()
    fixture = await build_execution_fixture(
        engine,
        tmp_path,
        mission_slug=mission_slug,
        task_class="verification",
    )
    advanced = await advance_task_to_verified(
        engine,
        tmp_path,
        tenant=fixture.tenant,
        task=fixture.task,
        context_package=fixture.context_package,
        route_decision=fixture.route_decision,
        write_files=write_files,
        idempotency_prefix=idempotency_prefix,
    )
    queue = IntegrationQueueService(engine, root=root)
    gates = DiffGateService(engine)
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
    result = await queue.integrate(proposal=proposal, workspace=advanced.workspace)
    return root, advanced, queue, gates, proposal, result


@pytest.mark.asyncio
async def test_schema_round_trip_persists_declared_columns(tmp_path: Path) -> None:
    """A row read back from `diff_gate_reports` validates against the
    generated contract with no drift (Chapter 3.1)."""
    engine = new_engine()
    root = repo_root()
    workspace = None
    task_branch = None
    mission_branch = None
    try:
        root, advanced, _queue, gates, proposal, merged = await _submit_and_integrate(
            engine,
            tmp_path,
            mission_slug="MISSION-GATE-SCHEMA",
            write_files={
                "engine/routing/dde021-schema.txt": b"diff-gate schema proof\n"
            },
            idempotency_prefix="dde021-schema",
        )
        workspace = advanced.workspace
        task_branch = f"task/{advanced.task.task_id}-a"
        mission_branch = f"mission/{advanced.task.mission_id}"
        assert merged.status == "MERGED"
        reports = await gates.list_for_proposal(
            tenant_id=advanced.task.tenant_id,
            project_id=advanced.task.project_id,
            proposal_id=proposal.proposal_id,
        )
        assert len(reports) == 1
        report = reports[0]
        assert report.status == "PASSED"
        assert report.quarantined is False
        reloaded = await gates.get_report(
            tenant_id=advanced.task.tenant_id,
            project_id=advanced.task.project_id,
            report_id=report.report_id,
        )
        assert reloaded == report
        assert gates.verify_sbom(report) is True
        components = report.sbom_document.get("components")
        assert isinstance(components, list)
        assert components, "SBOM must list declared-manifest components"
        assert report.sbom_document.get("bomFormat") == "CycloneDX"
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=root).cleanup(workspace=workspace)
        if task_branch is not None:
            git.delete_branch(root, task_branch)
        if mission_branch is not None:
            git.delete_branch(root, mission_branch)
        await engine.dispose()


@pytest.mark.asyncio
async def test_state_transition_evaluating_passed_via_clean_diff(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    root = repo_root()
    workspace = None
    task_branch = None
    mission_branch = None
    try:
        root, advanced, _queue, gates, proposal, merged = await _submit_and_integrate(
            engine,
            tmp_path,
            mission_slug="MISSION-GATE-PASSED",
            write_files={"engine/routing/dde021-clean.txt": b"clean\n"},
            idempotency_prefix="dde021-passed",
        )
        workspace = advanced.workspace
        task_branch = f"task/{advanced.task.task_id}-a"
        mission_branch = f"mission/{advanced.task.mission_id}"
        assert merged.status == "MERGED"
        reports = await gates.list_for_proposal(
            tenant_id=advanced.task.tenant_id,
            project_id=advanced.task.project_id,
            proposal_id=proposal.proposal_id,
        )
        assert reports[0].status == "PASSED"
        assert {item.gate for item in reports[0].findings} == {
            "secret_detection",
            "static_analysis",
            "dependency_vulnerability",
            "licence_header",
            "forbidden_path",
        }
        again = await gates.evaluate(
            proposal=proposal,
            repo_root=root,
            base_revision=reports[0].base_revision,
            proposed_revision=reports[0].proposed_revision,
            changed_paths=list(reports[0].changed_paths),
        )
        assert again.report_id == reports[0].report_id
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=root).cleanup(workspace=workspace)
        if task_branch is not None:
            git.delete_branch(root, task_branch)
        if mission_branch is not None:
            git.delete_branch(root, mission_branch)
        await engine.dispose()


@pytest.mark.asyncio
async def test_planted_secret_rejects_and_quarantines(tmp_path: Path) -> None:
    """Chapter 18.2 S2 fixture: diff gates block a planted secret."""
    engine = new_engine()
    root = repo_root()
    workspace = None
    task_branch = None
    mission_branch = None
    try:
        root, advanced, _queue, gates, proposal, rejected = await _submit_and_integrate(
            engine,
            tmp_path,
            mission_slug="MISSION-GATE-SECRET",
            write_files={
                "engine/routing/dde021-secret.txt": f"{PLANTED_SECRET}\n".encode()
            },
            idempotency_prefix="dde021-secret",
        )
        workspace = advanced.workspace
        task_branch = f"task/{advanced.task.task_id}-a"
        mission_branch = f"mission/{advanced.task.mission_id}"
        assert rejected.status == "REJECTED"
        assert rejected.conflict_class == "gate_failed"
        reports = await gates.list_for_proposal(
            tenant_id=advanced.task.tenant_id,
            project_id=advanced.task.project_id,
            proposal_id=proposal.proposal_id,
        )
        assert reports[0].status == "FAILED"
        assert reports[0].quarantined is True
        secret = next(
            item for item in reports[0].findings if item.gate == "secret_detection"
        )
        assert secret.passed is False
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=root).cleanup(workspace=workspace)
        if task_branch is not None:
            git.delete_branch(root, task_branch)
        if mission_branch is not None:
            git.delete_branch(root, mission_branch)
        await engine.dispose()


@pytest.mark.asyncio
async def test_planted_vulnerable_dependency_is_rejected(tmp_path: Path) -> None:
    """Chapter 18.2 S2 fixture: diff gates block a planted vulnerable
    dependency."""
    engine = new_engine()
    root = repo_root()
    workspace = None
    task_branch = None
    mission_branch = None
    try:
        root, advanced, _queue, gates, proposal, rejected = await _submit_and_integrate(
            engine,
            tmp_path,
            mission_slug="MISSION-GATE-VULN",
            write_files={
                "engine/routing/requirements.txt": b"dde-planted-vulnerable==0.0.1\n"
            },
            idempotency_prefix="dde021-vuln",
        )
        workspace = advanced.workspace
        task_branch = f"task/{advanced.task.task_id}-a"
        mission_branch = f"mission/{advanced.task.mission_id}"
        assert rejected.status == "REJECTED"
        assert rejected.conflict_class == "gate_failed"
        reports = await gates.list_for_proposal(
            tenant_id=advanced.task.tenant_id,
            project_id=advanced.task.project_id,
            proposal_id=proposal.proposal_id,
        )
        assert reports[0].status == "FAILED"
        admissions = await gates.list_admissions(
            tenant_id=advanced.task.tenant_id,
            project_id=advanced.task.project_id,
            report_id=reports[0].report_id,
        )
        assert len(admissions) == 1
        assert admissions[0].status == "REJECTED"
        assert "DDE-PLANTED-001" in admissions[0].vulnerability_ids
        assert admissions[0].package_name == "dde-planted-vulnerable"
        dep = next(
            item
            for item in reports[0].findings
            if item.gate == "dependency_vulnerability"
        )
        assert dep.passed is False
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=root).cleanup(workspace=workspace)
        if task_branch is not None:
            git.delete_branch(root, task_branch)
        if mission_branch is not None:
            git.delete_branch(root, mission_branch)
        await engine.dispose()


@pytest.mark.asyncio
async def test_unknown_report_is_policy_denied(tmp_path: Path) -> None:
    engine = new_engine()
    try:
        fixture = await build_execution_fixture(
            engine,
            tmp_path,
            mission_slug="MISSION-GATE-UNKNOWN",
            task_class="verification",
        )
        gates = DiffGateService(engine)
        with pytest.raises(DdeError) as exc:
            await gates.get_report(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                report_id=uuid7(),
            )
        assert exc.value.error_code == "POLICY_DENIED"
    finally:
        await engine.dispose()
