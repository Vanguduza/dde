"""`dde mission trace` recovery (Chapter 19.1): the command must read
everything it reports from durable PostgreSQL state, never from anything
held only in the writing process's memory.

The writer engine/connection pool that built the mission is fully disposed
-- simulating that process exiting -- *before* the trace is produced at all.
The trace itself is then produced by a real `python -m interfaces.cli`
subprocess: a brand-new OS process with its own fresh interpreter, engine
and connection pool that never shared any Python object with the writer.
Running it twice and getting byte-identical output is the proof that
everything in it came from committed rows, not process memory.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from engine.context.repo import repo_root
from engine.integration import git
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.mission_trace_fixtures import build_traceable_mission


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "interfaces.cli", *args],
        cwd=repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.asyncio
async def test_mission_trace_recovers_full_spine_after_writer_process_exits(
    tmp_path: Path,
) -> None:
    writer_engine = new_engine()
    trace = await build_traceable_mission(
        writer_engine, tmp_path, mission_slug="MISSION-CLI-TRACE-RECOVERY"
    )
    await writer_engine.dispose()  # simulate the writing process exiting

    try:
        first = _run_cli(
            "mission",
            "trace",
            str(trace.mission_id),
            "--tenant-id",
            str(trace.tenant.tenant_id),
        )
        assert first.returncode == 0, first.stderr

        # A second, wholly independent process/session reconstructs the
        # identical trace from the same durable rows -- nothing about the
        # first invocation's process left any state behind that mattered.
        second = _run_cli(
            "mission",
            "trace",
            str(trace.mission_id),
            "--tenant-id",
            str(trace.tenant.tenant_id),
        )
        assert second.returncode == 0, second.stderr
        assert first.stdout == second.stdout

        output = first.stdout
        assert str(trace.advanced.execution_plan.worker_profile_id) in output
        assert str(trace.advanced.verification_run.worker_run_id) in output
        assert str(trace.advanced.verification_run.verification_run_id) in output
        assert "Chapter 1 acceptance sentence: PROVEN" in output
    finally:
        root = repo_root()
        cleanup_engine = new_engine()
        try:
            await WorkspaceService(cleanup_engine, root=root).cleanup(
                workspace=trace.advanced.workspace
            )
        finally:
            await cleanup_engine.dispose()
        git.delete_branch(root, trace.task_branch)
        git.delete_branch(root, trace.mission_branch)
