"""`EnvironmentBackend` — the substrate-specific half of Chapter 7.3's
`type` field. `engine.environments.service.ExecutionEnvironmentService` (the
Provisioner) is substrate-agnostic; every backend implements this same
Protocol so a second backend (e.g. `docker`, out of this mission's scope)
slots in without changing the Provisioner or `engine.workspaces`.

Chapter 7.2 makes the ExecutionEnvironment the T2 enforcement boundary:
network policy, filesystem policy and resource limits are properties every
backend must report honestly. `IsolationReport` is how a backend declares
which of those it can actually enforce versus merely record — a backend must
never claim an isolation guarantee it does not implement (AGENTS.md: "Do not
fake" retryable side effects or "Silently widen ... network policy, or
filesystem policy").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from engine.capabilities.process_registry import RegisteredAuthority


@dataclass(frozen=True)
class EnvironmentSpec:
    """What the Provisioner asks a backend to provision. Mirrors the subset
    of Chapter 7.3's fields a backend is responsible for filling in."""

    environment_class: str
    resource_limits: dict[str, object]
    network_policy: dict[str, object]
    filesystem_policy: dict[str, object]


@dataclass(frozen=True)
class IsolationReport:
    """A backend's honest declaration of what it enforces versus what it
    only records (Chapter 7.2). Never fabricated to make a field look
    satisfied."""

    os_family: str
    architecture: str
    runtime_image: str
    image_digest: str
    toolchain_manifest: dict[str, object]
    toolchain_manifest_hash: str
    isolation_level: str
    network_policy: dict[str, object]
    filesystem_policy: dict[str, object]
    gaps: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ProvisionedEnvironment:
    """Live handle a backend returns from `provision()`. Not persisted
    verbatim — `ExecutionEnvironmentService` extracts the `IsolationReport`
    fields onto the `ExecutionEnvironment` row and keeps the handle only for
    the lifetime of the provisioning process."""

    environment_id_hint: str
    report: IsolationReport


@dataclass(frozen=True)
class CommandResult:
    """Real, captured outcome of one `execute()` call (Chapter 7.5). Never
    raised for a non-zero exit — a normal command failure is data, not an
    exception (Chapter 19.1's negative-test requirement: "subprocess failure
    ... is captured as a typed failure state, not an unhandled exception")."""

    command: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool


class EnvironmentBackend(Protocol):
    """One `type` value from Chapter 7.3. `docker`/`microvm`/etc. are valid
    enum members with no implementing backend in this mission."""

    def provision(self, spec: EnvironmentSpec) -> ProvisionedEnvironment: ...

    def run(
        self,
        *,
        cwd: Path,
        command: list[str],
        timeout_seconds: float,
    ) -> CommandResult:
        """Spawn a real process rooted at `cwd` and return its captured
        result. Must never raise for a non-zero exit or for exceeding
        `timeout_seconds` — both are represented in `CommandResult`."""
        ...

    async def run_for_authority(
        self,
        *,
        cwd: Path,
        command: list[str],
        timeout_seconds: float,
        authority: RegisteredAuthority,
    ) -> CommandResult:
        """The T2 revocation-latency twin of `run()` (Chapter 7.2:
        "revocation ... terminates the run"): spawn the same contained
        process while registering a live, revocable handle under the
        `(run, lease)` authority that authorized it, so
        `engine.capabilities.process_registry`'s arm-time sweep can
        terminate it mid-flight. Backends whose substrate cannot expose a
        revocable OS process handle (containers, remote executors) refuse
        here rather than silently registering nothing -- an unregistered
        spawn would be exactly the uninterruptible surface this method
        exists to close."""
        ...

    def teardown(self, handle: ProvisionedEnvironment) -> None: ...
