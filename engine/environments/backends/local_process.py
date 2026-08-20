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

**DDE-018 addition.** Chapter 7.2 T2 rule 1 ("Zero ambient credentials") is
scoped by the chapter to third-party agent harnesses with their own tool
planes — a caller class this codebase does not have yet (its one certified
worker, `engine.workers.scripted_adapter.ScriptedWorkerAdapter`, is
DDE-native and T1-brokered; see `engine.capabilities.seed.
SEED_CAPABILITIES`). Full T2 containment therefore still needs the
container/microVM backend this mission does not build. What this backend
*can* genuinely prove today, without a container: `run()` no longer hands a
worker-supplied command a verbatim copy of this process's own environment.
`_contained_environment()` passes through only the fixed, non-secret
variables an interpreter/shell genuinely needs to start on this OS —
`os.environ`'s remainder (where a real deployment's provider tokens, cloud
credentials and this repository's own `DDE_DATABASE_URL`/`DDE_REDIS_URL`
convention would live) is dropped, not merely unlogged. This is real and
narrow: it closes the ambient-*environment-variable* credential channel for
a worker-controlled `run()` call; it does not touch filesystem-based
credential stores (SSH agent socket, `.netrc`, credential-manager caches)
reachable via `USERPROFILE`/`APPDATA`, which remain a real, undischarged gap
— see `AMBIENT_ENVIRONMENT_GAP` below.
"""

from __future__ import annotations

import os
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

#: Chapter 7.2 T2 rule 1's real, load-bearing allowlist: the fixed set of
#: infrastructure variables a Python interpreter, `git`, or a shell
#: genuinely needs to start and operate on each OS family. Matched
#: case-insensitively (Windows environment variable names are
#: case-preserving but case-insensitive). Deliberately excludes
#: `USERPROFILE`/`HOME`/`APPDATA` — real dotfile/credential-manager
#: locations, not process-startup requirements (`AMBIENT_ENVIRONMENT_GAP`
#: names this as a residual gap rather than silently relying on it).
_WINDOWS_ALLOWED_ENV_VARS: frozenset[str] = frozenset(
    {
        "PATH",
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "TEMP",
        "TMP",
        "NUMBER_OF_PROCESSORS",
        "PROCESSOR_ARCHITECTURE",
        "PROCESSOR_IDENTIFIER",
    }
)
_POSIX_ALLOWED_ENV_VARS: frozenset[str] = frozenset(
    {"PATH", "TMPDIR", "LANG", "LC_ALL"}
)


def _allowed_env_var_names() -> frozenset[str]:
    return (
        _WINDOWS_ALLOWED_ENV_VARS
        if platform.system() == "Windows"
        else _POSIX_ALLOWED_ENV_VARS
    )


def _contained_environment() -> dict[str, str]:
    """Real replacement for handing `subprocess.run` a verbatim ambient
    environment (`env=None`, Python's default, means "inherit everything").
    Returns only the names in `_allowed_env_var_names()`, at whatever value
    they hold in this process — never a value invented for a name that
    was not actually set."""
    allowed = _allowed_env_var_names()
    return {
        name: value for name, value in os.environ.items() if name.upper() in allowed
    }


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
AMBIENT_ENVIRONMENT_GAP = (
    "run() passes a real, allowlisted environment-variable set (DDE-018), "
    "closing the ambient environment-variable credential channel for a "
    "worker-controlled command. It does not filter filesystem-based "
    "credential stores (SSH agent socket, .netrc, OS credential manager) "
    "reachable via the workspace path jail, which needs container/microVM "
    "isolation this backend does not implement."
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
            gaps=(NETWORK_ISOLATION_GAP, RESOURCE_LIMIT_GAP, AMBIENT_ENVIRONMENT_GAP),
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
                env=_contained_environment(),
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
