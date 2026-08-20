"""`dde mission create` / `mission status` / `task list` recovery (Chapter
19.1): every command must read (or, for `create`, write) through durable
PostgreSQL state alone, never through anything held only in a single
process's memory.

Mirrors `tests/recovery/test_cli_mission_trace_recovery.py`'s shape, but
goes one step further: here even the *write* (`mission create`) happens in
its own real subprocess, not merely the reads. Three independent `python -m
interfaces.cli` subprocesses -- one that creates the mission, two that read
it back -- never share a Python object; the only thing connecting them is
the committed row.
"""

from __future__ import annotations

import re
import subprocess
import sys
from uuid import uuid4

import pytest

from engine.context.repo import repo_root
from tests.support.db import new_engine, seed_tenant

_MISSION_ID_RE = re.compile(r"^mission_id: (?P<value>[0-9a-fA-F-]{36})$", re.MULTILINE)


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "interfaces.cli", *args],
        cwd=repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.asyncio
async def test_mission_created_in_one_process_recovers_in_fresh_processes() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
    finally:
        await engine.dispose()  # simulate the seeding process exiting

    slug = f"mission-cli-recovery-{uuid4().hex[:12]}"
    create_result = _run_cli(
        "mission",
        "create",
        "--tenant-id",
        str(tenant.tenant_id),
        "--project-id",
        str(tenant.project_id),
        "--slug",
        slug,
        "--title",
        "Recovery-fixture mission",
        "--intent",
        "Prove mission create/status/list survive a process boundary",
        "--success-definition",
        "Two fresh reader processes see byte-identical, durable state",
        "--autonomy-ceiling",
        "1",
    )
    assert create_result.returncode == 0, create_result.stderr
    match = _MISSION_ID_RE.search(create_result.stdout)
    assert match is not None, create_result.stdout
    mission_id = match.group("value")

    first_status = _run_cli(
        "mission", "status", mission_id, "--tenant-id", str(tenant.tenant_id)
    )
    second_status = _run_cli(
        "mission", "status", mission_id, "--tenant-id", str(tenant.tenant_id)
    )
    assert first_status.returncode == 0, first_status.stderr
    assert second_status.returncode == 0, second_status.stderr
    assert first_status.stdout == second_status.stdout
    assert slug in first_status.stdout
    assert "Tasks: 0 total" in first_status.stdout

    first_list = _run_cli(
        "task", "list", mission_id, "--tenant-id", str(tenant.tenant_id)
    )
    second_list = _run_cli(
        "task", "list", mission_id, "--tenant-id", str(tenant.tenant_id)
    )
    assert first_list.returncode == 0, first_list.stderr
    assert second_list.returncode == 0, second_list.stderr
    assert first_list.stdout == second_list.stdout
    assert "No tasks recorded for this mission yet." in first_list.stdout
