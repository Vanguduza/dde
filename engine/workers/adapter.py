"""Chapter 8.1's `WorkerAdapter` — "the single normative contract" every
worker integration implements. This module defines the Protocol and its
output value types only; no vendor SDK is imported here (AGENTS.md:
"`cursor_sdk` / `cursor-sdk-bridge` may be imported only from
`adapters/cursor/**`" — this module lives in `engine.workers` precisely
*because* it names the contract, not an implementation, mirroring
`engine.environments.backends.base.EnvironmentBackend`'s split between the
substrate-agnostic Protocol and its concrete backends).

Chapter 8.1's literal method signatures name three positional concepts
`prepare` receives: `execution_plan`, `context_ref`, `env_ref`. Nothing in
Chapters 3-9 defines a standalone "environment reference" object distinct
from the already-real `Workspace` this codebase has (Chapter 7.5,
DDE-010) — a `Workspace` already carries `execution_environment_id` plus
the one thing any real adapter (vendor-backed or scripted) actually needs to
act: a real filesystem path. `env_ref` is therefore typed as the concrete,
already-provisioned `Workspace` domain object here, not an opaque handle —
a flagged interpretation, not a chapter quotation, consistent with Chapter
7.2's model that Workspace/Environment binding is resolved by DDE before a
worker ever sees it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable
from uuid import UUID

from engine.contracts.execution_plan import ExecutionPlan
from engine.contracts.worker_run import WorkerRun
from engine.contracts.workspace import Workspace


@dataclass(frozen=True)
class WorkerAction:
    """The deterministic, non-AI instruction a Stage 1 scripted profile
    acts on (Chapter 8's WorkerAdapter is a contract over *some* worker
    harness; a real AI-model harness derives its own actions from
    model+context, which this mission explicitly does not build — see
    `engine.workers.scripted_adapter`). `command` is a real, literal
    argv to run inside the workspace (Chapter 7.5's `execute(command)`);
    `write_files` are literal byte contents written before the command
    runs, for profiles that need to demonstrate a real produced diff."""

    command: tuple[str, ...]
    write_files: dict[str, bytes] = field(default_factory=dict)
    timeout_seconds: float | None = None
    expected_artifact: str | None = None
    #: When set, this action is a Chapter 9 `capability.browser` probe
    #: (Playwright behind `adapters/playwright`), not a local-process argv.
    browser_url: str | None = None
    browser_expect_text: str | None = None
    #: DDE-045 `capability.security` scan mode (`sast`, or deferred
    #: `dast`/`agentic` which fail closed).
    security_mode: str | None = None
    #: DDE-048 `capability.android_analysis` scan mode (`static`, or
    #: deferred `dynamic`/`adb`/`instrumentation` which fail closed).
    android_mode: str | None = None


@dataclass(frozen=True)
class Registration:
    worker_id: str
    worker_profile_id: str
    declared_capabilities: frozenset[str]


@dataclass(frozen=True)
class WorkerHealth:
    healthy: bool
    detail: str


@dataclass(frozen=True)
class CapabilityManifest:
    capability_ids: frozenset[str]


@dataclass(frozen=True)
class PreparedRun:
    plan_id: UUID
    context_ref: UUID
    ready: bool
    detail: str


@dataclass(frozen=True)
class RunHandle:
    """Real, captured outcome of `start()` — never fabricated. Mirrors
    `engine.environments.backends.base.CommandResult`'s "never raise for a
    non-zero exit" convention: a scripted command failure is data the
    Worker Manager turns into a `FAILED` `WorkerRun`, not an exception."""

    run_id: UUID
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    changed_files: tuple[str, ...]
    diff_text: str


@dataclass(frozen=True)
class RunStatus:
    run_id: UUID
    state: str
    detail: str


@dataclass(frozen=True)
class PauseResult:
    accepted: bool
    reason: str


@dataclass(frozen=True)
class ResumeResult:
    accepted: bool
    reason: str


@dataclass(frozen=True)
class CheckpointRef:
    ref: str | None
    accepted: bool
    reason: str


@dataclass(frozen=True)
class CancelResult:
    accepted: bool
    reason: str


@dataclass(frozen=True)
class ArtifactManifest:
    changed_files: tuple[str, ...]
    diff_text: str


@dataclass(frozen=True)
class UsageRecord:
    duration_ms: int
    cost_usd: float


@dataclass(frozen=True)
class TerminationResult:
    terminated: bool
    detail: str


@dataclass(frozen=True)
class CleanupResult:
    cleaned: bool
    detail: str


@runtime_checkable
class WorkerAdapter(Protocol):
    """Chapter 8.1's fourteen-method contract, verbatim in name and
    intent. `engine.workers.registry.WorkerProfileRegistry` only accepts an
    implementation of this Protocol; Chapter 8.4's Worker Manager never
    calls anything not expressed through it."""

    async def register(self) -> Registration: ...

    async def health(self) -> WorkerHealth: ...

    async def capabilities(self) -> CapabilityManifest: ...

    async def prepare(
        self, *, execution_plan: ExecutionPlan, context_ref: UUID, env_ref: Workspace
    ) -> PreparedRun: ...

    async def start(self, worker_run: WorkerRun) -> RunHandle: ...

    async def status(self, worker_run: WorkerRun) -> RunStatus: ...

    async def request_pause(self, worker_run: WorkerRun) -> PauseResult: ...

    async def resume(
        self, worker_run: WorkerRun, checkpoint_ref: str | None
    ) -> ResumeResult: ...

    async def checkpoint(self, worker_run: WorkerRun) -> CheckpointRef: ...

    async def cancel(self, worker_run: WorkerRun, reason: str) -> CancelResult: ...

    async def collect_artifacts(self, worker_run: WorkerRun) -> ArtifactManifest: ...

    async def collect_usage(self, worker_run: WorkerRun) -> UsageRecord: ...

    async def terminate(self, worker_run: WorkerRun) -> TerminationResult: ...

    async def cleanup(self, worker_run: WorkerRun) -> CleanupResult: ...


@runtime_checkable
class ActionBindableWorkerAdapter(WorkerAdapter, Protocol):
    """A `WorkerAdapter` that also accepts an out-of-band `WorkerAction`
    (see `engine.workers.scripted_adapter`'s module docstring for why this
    exists outside the shared Chapter 8.1 Protocol: only a model-less,
    scripted profile needs its instruction delivered this way). `engine.
    workers.service.WorkerManagerService` checks for this narrower Protocol
    with `isinstance` rather than assuming every certified adapter supports
    it — a future AI-model-backed adapter legitimately would not."""

    def bind_action(self, execution_plan_id: UUID, action: WorkerAction) -> None: ...
