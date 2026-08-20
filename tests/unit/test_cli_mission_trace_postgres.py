"""`dde mission trace` end-to-end and negative tests (Chapter 19.1) --
the mission's literal acceptance test from Chapter 1: "The mission is only
successful when `dde mission trace` shows an evidence record produced by a
verification run that the generating worker did not control."

The happy-path test below invokes the real, installed entry point as a real
subprocess (`python -m interfaces.cli`, exactly as the console script's own
`dde = interfaces.cli.__main__:main` resolves) against a full mission built
through real production services (`tests.support.mission_trace_fixtures`) --
never a direct function call into this module's own internals -- so it
proves the actual CLI process, argument parsing and exit code, not just the
trace-building logic `tests/unit/test_cli_mission_trace.py` already covers
in isolation.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.context.repo import repo_root
from engine.contracts.evidence import Evidence
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.integration import git
from engine.missions.service import MissionService
from engine.truth.db import open_unit_of_work
from engine.verification.repository import EvidenceRepository
from engine.workspaces.service import WorkspaceService
from tests.support.db import TenantFixture, new_engine, seed_tenant
from tests.support.mission_trace_fixtures import (
    TraceableMission,
    build_traceable_mission,
)

EXIT_UNKNOWN_MISSION = 3
EXIT_INCOMPLETE = 4


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "interfaces.cli", *args],
        cwd=repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.asyncio
async def test_mission_trace_proves_generator_verifier_independence_and_evidence_hash(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    trace: TraceableMission | None = None
    try:
        trace = await build_traceable_mission(
            engine, tmp_path, mission_slug="MISSION-CLI-TRACE-HAPPY"
        )

        result = _run_cli(
            "mission",
            "trace",
            str(trace.mission_id),
            "--tenant-id",
            str(trace.tenant.tenant_id),
        )

        assert result.returncode == 0, result.stderr
        output = result.stdout

        generator = trace.advanced.execution_plan.worker_profile_id
        verifier_run_id = str(trace.advanced.verification_run.verification_run_id)
        generator_run_id = str(trace.advanced.verification_run.worker_run_id)
        evidence_rows = await _evidence_for(engine, trace)

        assert generator in output
        assert generator_run_id in output
        assert verifier_run_id in output
        assert evidence_rows
        assert any(row.content_hash in output for row in evidence_rows)
        assert "INDEPENDENT" in output
        assert (
            "Chapter 1 acceptance sentence: PROVEN -- at least one evidence "
            "record was produced by a verification run the generating worker "
            "did not control." in output
        )
    finally:
        if trace is not None:
            root = repo_root()
            await WorkspaceService(engine, root=root).cleanup(
                workspace=trace.advanced.workspace
            )
            git.delete_branch(root, trace.task_branch)
            git.delete_branch(root, trace.mission_branch)
        await engine.dispose()


async def _evidence_for(engine: AsyncEngine, trace: TraceableMission) -> list[Evidence]:
    """Re-read the real `Evidence` rows the fixture's `VerificationRun`
    produced, so the assertion above checks the actual persisted content
    hash rather than recomputing one independently."""
    async with open_unit_of_work(
        engine, tenant_id=trace.tenant.tenant_id, project_id=trace.tenant.project_id
    ) as uow:
        rows = await EvidenceRepository().list_for_run(
            uow.connection, trace.advanced.verification_run.verification_run_id
        )
        await uow.commit()
    return rows


@pytest.mark.asyncio
async def test_mission_trace_for_nonexistent_mission_id_exits_nonzero() -> None:
    """Negative test (Chapter 19.1): a syntactically valid but never-created
    mission_id is a clean, typed `UNKNOWN_MISSION` exit -- never a traceback
    or a silent empty trace."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        missing_mission_id = uuid7()

        result = _run_cli(
            "mission",
            "trace",
            str(missing_mission_id),
            "--tenant-id",
            str(tenant.tenant_id),
        )

        assert result.returncode == EXIT_UNKNOWN_MISSION
        assert "UNKNOWN_MISSION" in result.stderr
        assert "Traceback" not in result.stderr
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_mission_trace_for_mission_with_no_tasks_exits_nonzero() -> None:
    """Negative test (Chapter 19.1): a real, persisted mission that has no
    materialised TaskGraph/Task yet is genuinely incomplete data -- the
    command must print what it found and exit non-zero, not fabricate a
    trace or crash."""
    engine = new_engine()
    try:
        tenant: TenantFixture = await seed_tenant(engine)
        missions = MissionService(engine, EventService(engine))
        mission = await missions.create_mission(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            slug="mission-cli-trace-incomplete",
            title="Incomplete mission for the negative CLI test",
            intent="Prove `dde mission trace` refuses to fabricate a trace",
            success_definition="dde mission trace exits non-zero with a clear error",
            scope=["engine"],
            requirement_refs=[],
            autonomy_ceiling=1,
        )

        result = _run_cli(
            "mission",
            "trace",
            str(mission.mission_id),
            "--tenant-id",
            str(tenant.tenant_id),
        )

        assert result.returncode == EXIT_INCOMPLETE
        assert "MISSION_TRACE_INCOMPLETE" in result.stderr
        assert "Traceback" not in result.stderr
        # The command still prints whatever it genuinely found before
        # deciding the trace is incomplete (the mission header itself).
        assert str(mission.mission_id) in result.stdout
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_mission_trace_rejects_a_malformed_mission_id() -> None:
    """Negative test: a usage error (not a UUID) is a clean argparse-level
    exit, never an unhandled exception reaching the caller."""
    tenant_engine = new_engine()
    try:
        tenant = await seed_tenant(tenant_engine)
        result = _run_cli(
            "mission", "trace", "not-a-uuid", "--tenant-id", str(tenant.tenant_id)
        )
        assert result.returncode == 2
        assert "must be a UUID" in result.stderr
    finally:
        await tenant_engine.dispose()
