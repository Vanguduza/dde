"""`LocalProcessBackend` — Chapter 7.3 `type = "local"`.

The only implemented `EnvironmentBackend` in this mission (DDE-010). Spawns
a real OS subprocess rooted at a real filesystem directory (a `Workspace`,
provided by `engine.workspaces`, never created here). No container, microVM
or vendor SDK is involved.

Deliberately honest about what a plain OS process cannot do (AGENTS.md:
"Silently widening ... network policy, or filesystem policy" is forbidden).
Chapter 7.2's T2 containment — egress proxy, seccomp, non-privileged user,
size-capped `/tmp` — needs container/microVM isolation this backend does not
have; `provision()` records that gap on `IsolationReport.gaps` instead of
claiming enforcement it cannot deliver. The one guarantee a plain subprocess
call genuinely gives: a wall-clock timeout per `run()` invocation.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

from engine.core.hashing import canonical_json, sha256_hex
from engine.environments.backends.base import (
    CommandResult,
    EnvironmentSpec,
    IsolationReport,
    ProvisionedEnvironment,
)

RUNTIME_IMAGE = "local-process"

NETWORK_ISOLATION_GAP = (
    "network_policy is recorded but not enforced: a plain OS subprocess "
    "shares the host network stack. Chapter 7.2's T2 egress proxy requires "
    "container/microVM isolation (DDE-018, Stage 2), which this backend "
    "does not implement."
)
RESOURCE_LIMIT_GAP = (
    "resource_limits is recorded but only wall-clock timeout is enforced "
    "per run() call; no cgroup/Job Object memory or CPU ceiling is applied."
)


def _git_version() -> str:
    git = shutil.which("git")
    if git is None:
        return "unavailable"
    try:
        result = subprocess.run(  # noqa: S603
            [git, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except OSError:
        return "unavailable"
    return result.stdout.strip() or "unavailable"


class LocalProcessBackend:
    """`docker`/`microvm`/`vm`/`device`/`ci_runner`/`remote_api` (Chapter
    7.3's other `type` enum members) have no backend at all — not a stub,
    not a TODO — see `engine.environments.backends.__init__`."""

    def provision(self, spec: EnvironmentSpec) -> ProvisionedEnvironment:
        toolchain_manifest: dict[str, object] = {
            "python_version": sys.version,
            "platform": platform.platform(),
            "git_version": _git_version(),
        }
        toolchain_hash = sha256_hex(canonical_json(toolchain_manifest))
        report = IsolationReport(
            os_family=platform.system().lower() or "unknown",
            architecture=platform.machine() or "unknown",
            runtime_image=RUNTIME_IMAGE,
            image_digest=f"sha256:{toolchain_hash}",
            toolchain_manifest=toolchain_manifest,
            toolchain_manifest_hash=toolchain_hash,
            isolation_level="process",
            network_policy={**spec.network_policy, "enforced": False},
            filesystem_policy={
                **spec.filesystem_policy,
                "enforced": "workspace_root_path_jail_only",
            },
            gaps=(NETWORK_ISOLATION_GAP, RESOURCE_LIMIT_GAP),
        )
        return ProvisionedEnvironment(environment_id_hint=RUNTIME_IMAGE, report=report)

    def run(
        self, *, cwd: Path, command: list[str], timeout_seconds: float
    ) -> CommandResult:
        started = time.monotonic()
        try:
            completed = subprocess.run(  # noqa: S603
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            return CommandResult(
                command=tuple(command),
                exit_code=-1,
                stdout=exc.stdout if isinstance(exc.stdout, str) else "",
                stderr=exc.stderr if isinstance(exc.stderr, str) else "",
                duration_ms=duration_ms,
                timed_out=True,
            )
        except OSError as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            return CommandResult(
                command=tuple(command),
                exit_code=-1,
                stdout="",
                stderr=str(exc),
                duration_ms=duration_ms,
                timed_out=False,
            )
        duration_ms = int((time.monotonic() - started) * 1000)
        return CommandResult(
            command=tuple(command),
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_ms=duration_ms,
            timed_out=False,
        )

    def teardown(self, handle: ProvisionedEnvironment) -> None:
        """No persistent OS resource to release: this backend holds no
        container, VM or daemon handle between `run()` calls. Removing the
        workspace directory is `engine.workspaces.service.WorkspaceService.
        cleanup`'s job — Chapter 7.5: "Workspace creation, cleanup and
        recovery are performed by DDE, never by the worker" (nor by the
        environment backend)."""
        return None
