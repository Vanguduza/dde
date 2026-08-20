"""`dde mission create` / `dde mission status` / `dde task list` end-to-end
and negative tests (Chapter 19.1) -- DDE-015's general command surface,
tested the same way DDE-014's `tests/unit/test_cli_mission_trace_postgres.
py` tests `mission trace`: real, installed-entry-point subprocesses
(`python -m interfaces.cli`), real production services underneath, never a
direct function call into these modules' own internals for the
process-boundary assertions.

`dde mission create`'s happy path is verified by a *subsequent, independent*
read through `engine.missions.MissionsRepository` -- proving the command
persisted a real row, not merely printed a plausible-looking one (the
mission brief's explicit acceptance bar for this command).
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from engine.context.repo import repo_root
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.missions.repository import MissionsRepository
from engine.missions.service import MissionService
from engine.truth.db import open_unit_of_work
from tests.support.db import TenantFixture, new_engine, seed_tenant
from tests.support.execution_fixtures import build_execution_fixture

EXIT_UNKNOWN_MISSION = 3
EXIT_VALIDATION_ERROR = 5

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
async def test_mission_create_persists_a_real_row_independently_re_readable() -> None:
    """`mission create`'s literal acceptance bar: a real service call that
    produces a real, verifiable side effect -- proven here by re-reading
    the row through `MissionsRepository` from a wholly separate connection,
    not by trusting the command's own stdout."""
    engine = new_engine()
    try:
        tenant: TenantFixture = await seed_tenant(engine)
        slug = f"mission-cli-create-{uuid4().hex[:12]}"

        result = _run_cli(
            "mission",
            "create",
            "--tenant-id",
            str(tenant.tenant_id),
            "--project-id",
            str(tenant.project_id),
            "--slug",
            slug,
            "--title",
            "CLI-created mission",
            "--intent",
            "Prove dde mission create persists a real row",
            "--success-definition",
            "A subsequent independent read finds this mission",
            "--scope",
            "engine",
            "--scope",
            "tests",
            "--requirement-ref",
            "REQ-CLI-CREATE",
            "--autonomy-ceiling",
            "2",
        )

        assert result.returncode == 0, result.stderr
        match = _MISSION_ID_RE.search(result.stdout)
        assert match is not None, result.stdout
        mission_id = match.group("value")

        async with open_unit_of_work(
            engine, tenant_id=tenant.tenant_id, project_id=tenant.project_id
        ) as uow:
            reloaded = await MissionsRepository().get_mission(
                uow.connection, UUID(mission_id)
            )
            await uow.commit()

        assert reloaded is not None
        assert reloaded.slug == slug
        assert reloaded.title == "CLI-created mission"
        assert reloaded.status == "CREATED"
        assert reloaded.scope == ["engine", "tests"]
        assert reloaded.requirement_refs == ["REQ-CLI-CREATE"]
        assert reloaded.autonomy_ceiling == 2
        assert slug in result.stdout
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_mission_create_rejects_a_duplicate_slug_without_a_crash() -> None:
    """Negative test (Chapter 19.1): re-using an already-taken, project-
    unique slug is a real, typed `VERSION_CONFLICT` -- surfaced as a clean
    non-zero exit, never a traceback or a silently-overwritten row."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = MissionService(engine, EventService(engine))
        slug = f"mission-cli-dup-{uuid4().hex[:12]}"
        await service.create_mission(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            slug=slug,
            title="First mission with this slug",
            intent="Occupy the slug",
            success_definition="A second create with the same slug fails cleanly",
            scope=["engine"],
            requirement_refs=[],
            autonomy_ceiling=1,
        )

        result = _run_cli(
            "mission",
            "create",
            "--tenant-id",
            str(tenant.tenant_id),
            "--project-id",
            str(tenant.project_id),
            "--slug",
            slug,
            "--title",
            "Second mission with the same slug",
            "--intent",
            "Prove the CLI refuses a duplicate slug",
            "--success-definition",
            "Non-zero exit, no traceback",
            "--autonomy-ceiling",
            "1",
        )

        assert result.returncode == EXIT_VALIDATION_ERROR
        assert "VERSION_CONFLICT" in result.stderr
        assert "Traceback" not in result.stderr
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_mission_status_shows_real_task_counts_and_task_graph() -> None:
    engine = new_engine()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = await build_execution_fixture(
                engine, Path(tmp), mission_slug=f"MISSION-CLI-STATUS-{uuid4().hex[:8]}"
            )

        result = _run_cli(
            "mission",
            "status",
            str(fixture.mission.mission_id),
            "--tenant-id",
            str(fixture.tenant.tenant_id),
        )

        assert result.returncode == 0, result.stderr
        output = result.stdout
        assert str(fixture.mission.mission_id) in output
        assert f"slug={fixture.mission.slug!r}" in output
        assert "status=CREATED" in output
        assert "Tasks: 2 total" in output
        assert "TaskGraphs:" in output
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_mission_status_for_nonexistent_mission_id_exits_nonzero() -> None:
    """Negative test (Chapter 19.1): a syntactically valid but never-created
    mission_id is a clean, typed `UNKNOWN_MISSION` exit."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        missing_mission_id = uuid7()

        result = _run_cli(
            "mission",
            "status",
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
async def test_task_list_shows_real_persisted_tasks() -> None:
    engine = new_engine()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = await build_execution_fixture(
                engine,
                Path(tmp),
                mission_slug=f"MISSION-CLI-TASKLIST-{uuid4().hex[:8]}",
            )

        result = _run_cli(
            "task",
            "list",
            str(fixture.mission.mission_id),
            "--tenant-id",
            str(fixture.tenant.tenant_id),
        )

        assert result.returncode == 0, result.stderr
        output = result.stdout
        assert str(fixture.task.task_id) in output
        assert fixture.task.title in output
        assert "Total: 2 task(s)" in output
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_task_list_for_nonexistent_mission_id_exits_nonzero() -> None:
    """Negative test (Chapter 19.1): explicitly required by the mission
    brief -- `dde task list` for a nonexistent mission_id must produce a
    clear error and non-zero exit, never a crash or an empty-but-successful
    listing indistinguishable from a real mission with zero tasks."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        missing_mission_id = uuid7()

        result = _run_cli(
            "task",
            "list",
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
async def test_task_list_for_a_real_mission_with_no_tasks_yet_is_not_an_error() -> None:
    """A real mission that genuinely has no materialised tasks yet is a
    legitimate, zero-exit state -- distinct from `UNKNOWN_MISSION` above."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = MissionService(engine, EventService(engine))
        mission = await service.create_mission(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            slug=f"mission-cli-no-tasks-{uuid4().hex[:12]}",
            title="Mission with no tasks yet",
            intent="Prove an empty task list is not an error",
            success_definition="dde task list exits zero with an empty listing",
            scope=["engine"],
            requirement_refs=[],
            autonomy_ceiling=1,
        )

        result = _run_cli(
            "task",
            "list",
            str(mission.mission_id),
            "--tenant-id",
            str(tenant.tenant_id),
        )

        assert result.returncode == 0, result.stderr
        assert "No tasks recorded for this mission yet." in result.stdout
    finally:
        await engine.dispose()


def test_mission_create_rejects_a_malformed_tenant_id() -> None:
    """Negative test: a usage error (not a UUID) is a clean argparse-level
    exit, never an unhandled exception reaching the caller."""
    result = _run_cli(
        "mission",
        "create",
        "--tenant-id",
        "not-a-uuid",
        "--project-id",
        str(uuid4()),
        "--slug",
        "mission-cli-bad-uuid",
        "--title",
        "t",
        "--intent",
        "i",
        "--success-definition",
        "s",
        "--autonomy-ceiling",
        "1",
    )
    assert result.returncode == 2
    assert "must be a UUID" in result.stderr
