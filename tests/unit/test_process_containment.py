"""Live local-process containment (Chapter 7.2 T2 revocation latency) --
pure unit tests over `engine.capabilities.process_registry` and
`engine.environments.backends.local_process.LocalProcessBackend.
run_for_authority`, no PostgreSQL.

Production seams under test: the environment backend's authority-scoped
spawn registers a revocable handle keyed by `(run, lease)` in a process
registry, and `sweep_run` terminates registered live pids with an honest
per-pid outcome (`terminated`/`killed`/`absent`/`failed`). These are REAL
subprocesses -- real OS children of pytest -- so every liveness assertion
here is about genuine processes, never mocks.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest

from engine.capabilities.process_registry import (
    SHARED_PROCESS_REGISTRY,
    ProcessHandleRegistry,
    RegisteredAuthority,
    RegisteredProcess,
)
from engine.environments.backends.base import CommandResult
from engine.environments.backends.local_process import LocalProcessBackend

TENANT = uuid4()
PROJECT = uuid4()
RUN = uuid4()
LEASE = uuid4()

_SLOW_EXIT_COMMAND = [sys.executable, "-c", "import time; time.sleep(30)"]


class FreshRegistry(ProcessHandleRegistry):
    """Per-test registry instance; the shared default must stay untouched
    by tests."""


def _authority() -> RegisteredAuthority:
    return RegisteredAuthority(
        tenant_id=TENANT,
        project_id=PROJECT,
        worker_run_id=RUN,
        capability_lease_id=LEASE,
    )


def _handle(pid: int) -> RegisteredProcess:
    return RegisteredProcess(
        tenant_id=TENANT,
        project_id=PROJECT,
        worker_run_id=RUN,
        capability_lease_id=LEASE,
        pid=pid,
        created_at=time.monotonic(),
    )


def _alive(pid: int) -> bool:
    """Platform-honest liveness probe for test assertions. POSIX: signal 0
    is the conventional existence check. Windows: signal 0 would KILL the
    target (`os.kill` maps to TerminateProcess there), so existence goes
    through OpenProcess instead."""
    if sys.platform == "win32":
        import ctypes
        import ctypes.wintypes

        handle = ctypes.windll.kernel32.OpenProcess(
            0x1000,  # PROCESS_QUERY_LIMITED_INFORMATION
            False,
            pid,
        )
        if not handle:
            return False
        code = ctypes.wintypes.DWORD()
        observed = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        if not observed:
            return True
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _reap(proc: subprocess.Popen[bytes]) -> None:
    """Hard cleanup so no orphan outlives a test."""
    try:
        proc.kill()
    except OSError:
        pass
    try:
        proc.wait(timeout=5)
    except (subprocess.TimeoutExpired, OSError):
        pass


async def test_sweep_terminates_registered_live_process_and_reports_outcome() -> None:
    """The core mechanic: a real sleeping child registered under its run
    stops existing after the sweep, and the outcome honestly names what
    happened (`terminated` where SIGTERM is deliverable, `killed`
    otherwise -- Windows has no graceful phase)."""
    registry = FreshRegistry()
    proc = subprocess.Popen(  # noqa: S603, ASYNC220
        _SLOW_EXIT_COMMAND, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    registry.register(_handle(proc.pid))
    try:
        outcomes = await registry.sweep_run(
            tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN
        )
    finally:
        _reap(proc)
    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.pid == proc.pid
    assert outcome.phase in {"terminated", "killed"}
    assert _alive(proc.pid) is False


async def test_sweep_reports_absent_for_already_exited_pid() -> None:
    """An exited pid contributes an honest `absent` outcome and raises
    nothing."""
    registry = FreshRegistry()
    proc = subprocess.Popen(  # noqa: S603, ASYNC220
        [sys.executable, "-c", "pass"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    proc.wait()
    registry.register(_handle(proc.pid))
    outcomes = await registry.sweep_run(
        tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN
    )
    assert [outcome.phase for outcome in outcomes] == ["absent"]


async def test_registry_scoping_isolates_runs() -> None:
    """Keying discipline: sweeping one run touches only that run's handles;
    another run's live process survives untouched."""
    other_run = uuid4()
    other_lease = uuid4()
    registry = FreshRegistry()
    mine = subprocess.Popen(  # noqa: S603, ASYNC220
        _SLOW_EXIT_COMMAND, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    other = subprocess.Popen(  # noqa: S603, ASYNC220
        _SLOW_EXIT_COMMAND, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    registry.register(_handle(mine.pid))
    registry.register(
        RegisteredProcess(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=other_run,
            capability_lease_id=other_lease,
            pid=other.pid,
            created_at=time.monotonic(),
        )
    )
    try:
        assert [
            item.pid
            for item in registry.list_for_run(
                tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN
            )
        ] == [mine.pid]
        outcomes = await registry.sweep_run(
            tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN
        )
        assert [outcome.pid for outcome in outcomes] == [mine.pid]
        assert _alive(other.pid) is True
    finally:
        _reap(mine)
        _reap(other)

    registry.unregister(
        tenant_id=TENANT, project_id=PROJECT, worker_run_id=other_run, pid=other.pid
    )
    assert (
        registry.list_for_run(
            tenant_id=TENANT, project_id=PROJECT, worker_run_id=other_run
        )
        == []
    )


async def test_run_for_authority_registers_while_running_then_unregisters(
    tmp_path: Path,
) -> None:
    """The spawn seam: while the child runs it IS visible under its
    `(run, lease)` key with the authorizing lease id; after natural
    completion the registry is empty -- deregistration is real."""
    registry = FreshRegistry()
    backend = LocalProcessBackend(registry=registry)
    slow = [sys.executable, "-c", "import time; time.sleep(5); print('done')"]
    task = asyncio.create_task(
        backend.run_for_authority(
            cwd=tmp_path, command=slow, timeout_seconds=30.0, authority=_authority()
        )
    )
    await asyncio.sleep(0.5)
    live = registry.list_for_run(
        tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN
    )
    assert len(live) == 1
    assert live[0].capability_lease_id == LEASE

    result = await task
    assert (
        SHARED_PROCESS_REGISTRY.list_for_run(
            tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN
        )
        == []
    )
    assert isinstance(result, CommandResult)
    assert result.exit_code == 0
    assert "done" in result.stdout
    assert (
        registry.list_for_run(tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN)
        == []
    )


async def test_armed_stop_reaches_a_registered_in_flight_process(
    tmp_path: Path,
) -> None:
    """The end-to-end gap closure, at the mechanics level: a mid-flight
    lease-scoped child exists, the sweep fires, the child stops existing --
    Chapter 7.2's "revocation ... terminates the run", proven against real
    OS processes. The terminated child surfaces through the same typed
    `CommandResult` shape -- data, never an exception."""
    registry = FreshRegistry()
    backend = LocalProcessBackend(registry=registry)
    task = asyncio.create_task(
        backend.run_for_authority(
            cwd=tmp_path,
            command=_SLOW_EXIT_COMMAND,
            timeout_seconds=60.0,
            authority=_authority(),
        )
    )
    await asyncio.sleep(0.5)
    live = registry.list_for_run(
        tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN
    )
    assert len(live) == 1
    pid = live[0].pid

    outcomes = await registry.sweep_run(
        tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN
    )
    assert [outcome.pid for outcome in outcomes] == [pid]
    assert outcomes[0].phase in {"terminated", "killed"}
    assert _alive(pid) is False

    result = await task
    assert result.exit_code != 0
    assert result.timed_out is False


async def test_timeout_of_an_authority_spawn_hard_stops_the_child(
    tmp_path: Path,
) -> None:
    """A per-invocation timeout still hard-stops the authority-scoped child
    and returns the timed-out `CommandResult` shape, with the registry left
    empty."""
    registry = FreshRegistry()
    backend = LocalProcessBackend(registry=registry)
    result = await backend.run_for_authority(
        cwd=tmp_path,
        command=_SLOW_EXIT_COMMAND,
        timeout_seconds=0.5,
        authority=_authority(),
    )
    assert result.timed_out is True
    assert result.exit_code == -1
    assert (
        registry.list_for_run(tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN)
        == []
    )


async def test_grandchild_survives_the_sweep_and_is_disclosed(tmp_path: Path) -> None:
    """The honest residual, proven rather than claimed: the sweep kills the
    registered child, but a grandchild the command spawned itself is NOT
    registered and therefore survives. This is exactly what EDR-0011's
    container-level work would gate; until then the limit stays disclosed
    in the docstrings."""
    registry = FreshRegistry()
    backend = LocalProcessBackend(registry=registry)
    spawn_grandchild = [
        sys.executable,
        "-u",
        "-c",
        (
            "import subprocess, sys, time;"
            "p = subprocess.Popen([sys.executable, '-c', "
            "'import time; time.sleep(60)']);"
            "print(p.pid);"
            "time.sleep(60)"
        ),
    ]
    task = asyncio.create_task(
        backend.run_for_authority(
            cwd=tmp_path,
            command=spawn_grandchild,
            timeout_seconds=60.0,
            authority=_authority(),
        )
    )
    await asyncio.sleep(1.5)
    live = registry.list_for_run(
        tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN
    )
    assert len(live) == 1
    await registry.sweep_run(tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN)
    result = await task
    grandchild_pid = int(result.stdout.strip())
    try:
        assert _alive(grandchild_pid) is True
    finally:
        if sys.platform == "win32":
            subprocess.run(  # noqa: S603, ASYNC221
                ["taskkill", "/PID", str(grandchild_pid), "/F"],  # noqa: S607
                capture_output=True,
                check=False,
            )
        else:
            try:
                os.kill(grandchild_pid, 15)
            except OSError:
                pass
        await asyncio.to_thread(_join_pid, grandchild_pid)


def _join_pid(pid: int) -> None:
    """Best-effort reap of a test-spawned non-child pid: wait until gone."""
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if not _alive(pid):
            return
        time.sleep(0.1)


@pytest.mark.parametrize("platform_name", [sys.platform])
async def test_windows_signal_zero_trap_is_avoided(platform_name: str) -> None:
    """Regression pin for the classic Windows trap: `os.kill(pid, 0)` on
    win32 is TerminateProcess semantics and would KILL the target. The
    registry's Windows path must probe via OpenProcess instead -- proven by
    sweeping a live pid twice: the first sweep reports the kill, the second
    reports `absent` (a signal-0-based probe would have misreported the
    first phase as graceful and left inconsistent bookkeeping)."""
    if platform_name != "win32":
        pytest.skip("Windows-specific regression pin")
    registry = FreshRegistry()
    proc = subprocess.Popen(  # noqa: S603, ASYNC220
        _SLOW_EXIT_COMMAND, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    registry.register(_handle(proc.pid))
    try:
        first = await registry.sweep_run(
            tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN
        )
        second = await registry.sweep_run(
            tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN
        )
    finally:
        _reap(proc)
    assert first[0].phase == "killed"  # never dressed up as "terminated"
    assert second[0].phase == "absent"
