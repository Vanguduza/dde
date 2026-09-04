"""Live local-process containment (Chapter 7.2 T2 revocation latency).

**The gap this closes.** Arming a run's stop (`engine.capabilities.
lease_service.CapabilityLeaseService.arm_run_stop`) already revokes held
leases, broker handles and NEW credential admission -- but an in-flight
subprocess spawned under the run's lease kept running with whatever secret
material its environment carried until its own completion. Chapter 7.2's
T2 revocation-latency column promises more: "revocation ... terminates the
run". This module is that promise for the one substrate this repository
has (`engine.environments.backends.local_process.LocalProcessBackend`,
whose `run_for_authority` registers every authority-scoped spawn here):
the arm-time sweep terminates registered live processes of the stopped
run.

**Keying and source of truth.** Handles are keyed by the authority tuple
that authorized the spawn -- `(tenant_id, project_id, worker_run_id,
capability_lease_id)` plus the OS pid -- mirroring the `external_effects`
journal columns (`worker_run_id`, `capability_lease_id` are Chapter 12.4's
own keys) so a termination can be journalled against exactly the
lease-scoped mutation identity the recovery rule already speaks. Like
`KillSwitchRegistry`, this registry is deliberately IN-MEMORY and
per-instance-cache-shaped: it tracks only live OS resources of THIS
process (a restart legitimately loses them -- its children died with its
bookkeeping or were never this instance's), never authority state itself.
It introduces no table, no schema change, and no second source of truth
for any durable fact.

**Termination mechanics (stdlib only -- no psutil, no new dependency;
Chapter 9.6).** Escalation per pid: a graceful request (POSIX `SIGTERM`),
a bounded grace window, a forced kill (POSIX `SIGKILL`; Windows
`TerminateProcess`), then a bounded awaited exit and best-effort reaping.
Windows has no deliverable graceful signal: `os.kill(pid, sig)` there is
itself `TerminateProcess` (and `os.kill(pid, 0)` would KILL the target --
the classic trap this module avoids by probing through
`OpenProcess`/`GetExitCodeProcess` instead), so on Windows every phase is
hard-kill and outcomes honestly report `killed`, never `terminated`.
"Tree" reach is best-effort within stdlib: the direct child is what this
module registered; grandchildren the command spawned itself can outlive
the kill on either platform (no Job Object on Windows -- creating one
needs `pywin32`; no process-group detachment contract on POSIX), and that
residual is disclosed rather than hidden -- full tree/container isolation
is exactly the T2 container work EDR-0011 proposes. Sweeping is
best-effort BY CONSTRUCTION: a pid that already exited reports `absent`;
one that survives every attempt reports `failed` with the OS error text --
never a raised exception failing the stop. All blocking OS calls run
through `asyncio.to_thread`, so a sweep inside an async transaction never
blocks the event loop.
"""

from __future__ import annotations

import asyncio
import signal
import sys
import threading
import time
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

#: Grace window between the graceful request and the forced kill, and the
#: ceiling for awaiting exit after the forced kill. No chapter names a
#: literal duration; this mirrors the bounded-timeout discipline
#: `LocalProcessBackend.run` already applies per invocation.
TERMINATION_GRACE_SECONDS = 5.0

#: Journal vocabulary for the arm-time sweep's external-effect rows
#: (`target_system` / `operation`). A distinct system constant -- not
#: `local_process`'s -- so a sweep row can never collide with (nor block,
#: via the recovery scope gate) a later legitimate
#: `capability.run_local_process` mutation, while still carrying the run
#: and lease identity Chapter 12.4 journals effects under. The reason
#: itself reuses the kill-flag reason so every artifact of one intentional
#: stop names the same cause.
PROCESS_KILL_TARGET_SYSTEM = "process_termination"
PROCESS_KILL_OPERATION = "terminate_run_processes"

_TERMINATE_POLL_INTERVAL_SECONDS = 0.05


@dataclass(frozen=True)
class RegisteredAuthority:
    """The lease identity authorizing a spawn -- what a caller presents so
    the environment backend can register the resulting pid against exactly
    the scope a later stop sweeps."""

    tenant_id: UUID
    project_id: UUID
    worker_run_id: UUID
    capability_lease_id: UUID


@dataclass(frozen=True)
class RegisteredProcess:
    """One live, revocable handle to a run-scoped subprocess."""

    tenant_id: UUID
    project_id: UUID
    worker_run_id: UUID
    capability_lease_id: UUID
    pid: int
    created_at: float


@dataclass(frozen=True)
class TerminationOutcome:
    """Honest per-pid result of a sweep attempt. `phase`:
    `terminated` -- graceful signal accepted and the process exited within
    the grace window; `killed` -- forced escalation was required (always
    the case on Windows, which has no graceful phase);
    `absent` -- the pid had already exited or is not visible to this user;
    `failed` -- the OS refused every attempt. `detail` carries the
    exception text verbatim for `failed`."""

    pid: int
    phase: str
    detail: str | None = None


class _ProcessTerminator(Protocol):
    """One pid-specific termination surface over the OS APIs. Implemented
    per platform below; every method may raise `OSError`, which callers
    translate into a `failed` outcome rather than propagating."""

    @property
    def graceful(self) -> bool:
        """Whether `signal_request` is a cooperative signal the process can
        handle (POSIX SIGTERM) versus an immediate hard kill (Windows)."""
        ...

    def signal_request(self) -> None:
        """Phase 1: ask the process to stop."""
        ...

    def force_kill(self) -> None:
        """Phase 2: unconditional termination."""
        ...

    def is_running(self) -> bool:
        """Liveness of the pid. Conservative on ambiguity: reports running."""
        ...

    def await_exit(self, timeout_seconds: float) -> None:
        """Block until the pid exits; raise `TimeoutError` past
        `timeout_seconds`."""
        ...

    def reap(self) -> None:
        """Best-effort release of the pid's resources/handle."""
        ...


if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

    _PROCESS_TERMINATE = 0x0001
    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _SYNCHRONIZE = 0x00100000
    _STILL_ACTIVE = 259
    _WAIT_TIMEOUT = 0x00000102

    class _WindowsTerminator:
        """Hard-kill-only terminator: Windows exposes no deliverable
        graceful signal to stdlib callers, so every phase is
        `TerminateProcess` (exit code 1)."""

        def __init__(self, pid: int, handle: object) -> None:
            self._pid = pid
            self._handle = handle

        @property
        def graceful(self) -> bool:
            return False

        def signal_request(self) -> None:
            self.force_kill()

        def force_kill(self) -> None:
            if not ctypes.windll.kernel32.TerminateProcess(self._handle, 1):
                raise OSError("TerminateProcess refused")

        def is_running(self) -> bool:
            code = ctypes.wintypes.DWORD()
            if not ctypes.windll.kernel32.GetExitCodeProcess(
                self._handle, ctypes.byref(code)
            ):
                # Cannot observe: assume still running (conservative).
                return True
            return code.value == _STILL_ACTIVE

        def await_exit(self, timeout_seconds: float) -> None:
            timeout_ms = max(int(timeout_seconds * 1000), 1)
            result = ctypes.windll.kernel32.WaitForSingleObject(
                self._handle, timeout_ms
            )
            if result == _WAIT_TIMEOUT:
                raise TimeoutError(f"pid {self._pid} did not exit within grace window")
            if not self._exit_code_observed():
                raise OSError("GetExitCodeProcess refused after exit")

        def _exit_code_observed(self) -> bool:
            code = ctypes.wintypes.DWORD()
            return bool(
                ctypes.windll.kernel32.GetExitCodeProcess(
                    self._handle, ctypes.byref(code)
                )
            )

        def reap(self) -> None:
            ctypes.windll.kernel32.CloseHandle(self._handle)

    def _open_terminator(pid: int) -> _ProcessTerminator | None:
        handle = ctypes.windll.kernel32.OpenProcess(
            _PROCESS_TERMINATE | _PROCESS_QUERY_LIMITED_INFORMATION | _SYNCHRONIZE,
            False,
            pid,
        )
        if not handle:
            # Includes already-exited pids and access-denied ones; the
            # latter surfaces as `failed` only if a later phase proves it
            # observable-but-unsignallable, which cannot happen without a
            # handle -- hence honest `absent`.
            return None
        return _WindowsTerminator(pid, handle)

else:
    import os

    class _PosixTerminator:
        def __init__(self, pid: int) -> None:
            self._pid = pid
            #: Set once `is_running`/`await_exit` has reaped this child, so
            #: a later probe cannot mistake a recycled pid for this one.
            self._reaped = False

        @property
        def graceful(self) -> bool:
            return True

        def signal_request(self) -> None:
            os.kill(self._pid, signal.SIGTERM)

        def force_kill(self) -> None:
            os.kill(self._pid, signal.SIGKILL)

        def is_running(self) -> bool:
            # A child that has exited but has not yet been reaped is a
            # ZOMBIE, and a zombie still answers signal 0 -- so the bare
            # existence probe reports it alive forever. Since the sweep
            # terminates processes DDE itself spawned, that is the common
            # case, not an edge case: without reaping first, a perfectly
            # well-behaved child that honoured SIGTERM would sit out the
            # whole grace window and then be needlessly SIGKILLed and
            # recorded as `killed` rather than `terminated`.
            #
            # So: reap non-blockingly first. `waitpid` returning our pid
            # means it has exited (and is now reaped); 0 means genuinely
            # still running. Only when the pid is not our child does the
            # existence probe below decide.
            if self._reaped:
                return False
            try:
                done, _status = os.waitpid(self._pid, os.WNOHANG)
            except ChildProcessError:
                pass  # not our child (or already reaped elsewhere)
            else:
                if done == self._pid:
                    self._reaped = True
                    return False
                return True
            try:
                os.kill(self._pid, 0)
            except ProcessLookupError:
                return False
            except PermissionError:
                return True
            return True

        def await_exit(self, timeout_seconds: float) -> None:
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                try:
                    done, _status = os.waitpid(self._pid, os.WNOHANG)
                except ChildProcessError:
                    # Not our child: fall back to the existence probe.
                    if not self.is_running():
                        return
                else:
                    if done == self._pid:
                        self._reaped = True
                        return
                time.sleep(_TERMINATE_POLL_INTERVAL_SECONDS)
            raise TimeoutError(f"pid {self._pid} did not exit within grace window")

        def reap(self) -> None:
            if self._reaped:
                return
            try:
                os.waitpid(self._pid, os.WNOHANG)
            except (ChildProcessError, OSError):
                pass
            else:
                self._reaped = True

    def _open_terminator(pid: int) -> _ProcessTerminator | None:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return None
        except PermissionError:
            pass  # alive but owned by another user; the signals themselves decide
        return _PosixTerminator(pid)


def _terminate_authority_process(pid: int) -> str:
    """Blocking terminate -> grace -> kill -> reap for ONE pid. Returns the
    phase string recorded on the outcome; raises `OSError`/`TimeoutError`
    when the OS refuses every attempt (surfaced as a `failed` outcome)."""
    terminator = _open_terminator(pid)
    if terminator is None:
        return "absent"
    graceful_capable = terminator.graceful
    try:
        terminator.signal_request()
    except OSError:
        if not terminator.is_running():
            terminator.reap()
            return "absent"
        raise
    deadline = time.monotonic() + TERMINATION_GRACE_SECONDS
    while time.monotonic() < deadline:
        if not terminator.is_running():
            terminator.reap()
            # Windows' phase 1 is already a hard kill; never dress it up
            # as a graceful termination.
            return "terminated" if graceful_capable else "killed"
        time.sleep(_TERMINATE_POLL_INTERVAL_SECONDS)
    try:
        terminator.force_kill()
    except OSError:
        if not terminator.is_running():
            return "killed"
        raise
    terminator.await_exit(TERMINATION_GRACE_SECONDS)
    terminator.reap()
    return "killed"


class ProcessHandleRegistry:
    """Thread-safe, in-memory registry of live run-scoped subprocesses.
    Writers: the environment backend at spawn registration and at natural
    exit. Reader-sweeper: the lease service's arm-time stop. Persists
    nothing."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        #: (tenant_id, project_id, worker_run_id) -> {pid: RegisteredProcess}
        self._by_run: dict[tuple[UUID, UUID, UUID], dict[int, RegisteredProcess]] = {}

    def register(self, handle: RegisteredProcess) -> None:
        with self._lock:
            run_key = (handle.tenant_id, handle.project_id, handle.worker_run_id)
            self._by_run.setdefault(run_key, {})[handle.pid] = handle

    def unregister(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        worker_run_id: UUID,
        pid: int,
    ) -> None:
        """Drop one handle -- called by the spawning backend in a `finally`
        when the process exits on its own, so the registry holds only live
        pids. Removing a handle the sweeper killed is equally correct: the
        resource no longer exists either way."""
        with self._lock:
            bucket = self._by_run.get((tenant_id, project_id, worker_run_id))
            if bucket is not None:
                bucket.pop(pid, None)
                if not bucket:
                    self._by_run.pop((tenant_id, project_id, worker_run_id), None)

    def list_for_run(
        self, *, tenant_id: UUID, project_id: UUID, worker_run_id: UUID
    ) -> list[RegisteredProcess]:
        with self._lock:
            bucket = self._by_run.get((tenant_id, project_id, worker_run_id))
            if bucket is None:
                return []
            return list(bucket.values())

    async def sweep_run(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        worker_run_id: UUID,
    ) -> list[TerminationOutcome]:
        """Terminate every currently-registered live process of the run,
        concurrently, each via the blocking escalate-in-thread helper. A
        per-pid failure becomes an honest `failed` outcome -- the sweep
        never raises for an individual stubborn pid."""
        handles = self.list_for_run(
            tenant_id=tenant_id, project_id=project_id, worker_run_id=worker_run_id
        )
        if not handles:
            return []
        attempts = [self._attempt(handle) for handle in handles]
        return list(await asyncio.gather(*attempts))

    async def _attempt(self, handle: RegisteredProcess) -> TerminationOutcome:
        try:
            phase = await asyncio.to_thread(_terminate_authority_process, handle.pid)
        except (OSError, TimeoutError) as exc:
            return TerminationOutcome(pid=handle.pid, phase="failed", detail=str(exc))
        return TerminationOutcome(pid=handle.pid, phase=phase)


#: Process-wide registry backing `LocalProcessBackend.run_for_authority`'s
#: registrations and `CapabilityLeaseService.arm_run_stop`'s sweep --
#: module-level so a stop armed through any service instance reaches every
#: registration in the process, exactly like
#: `engine.capabilities.lease_service.SHARED_KILL_SWITCH`. The DURABLE
#: artifacts of a stop remain the ledger row, the REVOKED lease rows and
#: the external-effect journal; this registry holds only live OS pids.
SHARED_PROCESS_REGISTRY = ProcessHandleRegistry()
