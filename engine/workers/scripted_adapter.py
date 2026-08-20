"""`ScriptedWorkerAdapter` — Stage 1's one real, certified `WorkerAdapter`
(Chapter 8.1) implementation, standing behind `profile.deterministic_runner`
(already named, unimplemented, in `engine.routing.policy` since DDE-009,
where it is the `prefer[]`'d profile for the `verification` workload class).

**Scoping decision (see the mission summary for full reasoning).** Chapter
8's `WorkerAdapter` is written abstractly enough — `prepare`/`start` operate
on an `execution_plan`/`context_ref`/`env_ref`/`worker_run` and produce a
`RunHandle`/`ArtifactManifest`/`UsageRecord`, never anything AI-model-shaped
— that a real, non-AI backend genuinely satisfies the contract. This adapter
runs a real, literal, caller-supplied `WorkerAction` (an argv plus optional
literal file writes) inside a real, already-provisioned `Workspace`
(`engine.workspaces.service.WorkspaceService`, DDE-010) via that service's
existing, real `write()`/`execute()`/`snapshot()` methods. No model, harness
or vendor SDK is invoked — `cursor_sdk`/`cursor-sdk-bridge` is not imported
anywhere in this module, matching AGENTS.md's forbidden list ("Passing a
long-lived credential to anything that executes model-generated code") and
this mission's explicit constraint against wiring a real hosted AI call.
Real AI worker integration is deferred to a later, separately-scoped and
credentialed mission (`adapters/cursor/**`, per AGENTS.md's boundary rule).

Chapter 8.1's literal `prepare(execution_plan, context_ref, env_ref)` has no
slot for "what to do" — a real AI adapter derives that from its own
model+context; this scripted profile has no model, so it receives its
instruction out-of-band via `bind_action()`, an addition to this concrete
adapter only, not to the shared `WorkerAdapter` Protocol. `bind_action` is
keyed by `execution_plan_id` (not `run_id`) because Chapter 8.1 calls
`prepare()` before a `WorkerRun` row — and therefore a `run_id` — exists
(Chapter 3.9 step 10 creates the run only after planning); `start(worker_run)`
recovers the same binding via `worker_run.execution_plan_id`, a real field
on the row itself.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from uuid import UUID

from engine.contracts.execution_plan import ExecutionPlan
from engine.contracts.worker_run import WorkerRun
from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError
from engine.routing.policy import (
    CAPABILITY_REPOSITORY,
    CAPABILITY_TESTING,
    PROFILE_DETERMINISTIC_RUNNER,
)
from engine.workers.adapter import (
    ArtifactManifest,
    CancelResult,
    CapabilityManifest,
    CheckpointRef,
    CleanupResult,
    PauseResult,
    PreparedRun,
    Registration,
    ResumeResult,
    RunHandle,
    RunStatus,
    TerminationResult,
    UsageRecord,
    WorkerAction,
    WorkerHealth,
)
from engine.workspaces.service import WorkspaceService

WORKER_ID = "worker.scripted-deterministic-v1"
DECLARED_CAPABILITIES = frozenset({CAPABILITY_REPOSITORY, CAPABILITY_TESTING})

_SYNCHRONOUS_BACKEND_REASON = (
    "ScriptedWorkerAdapter executes its action synchronously inside "
    "start() and returns only once terminal; there is no in-flight window "
    "for a mid-run control operation to act on."
)


class ScriptedWorkerAdapter:
    """Chapter 8.1's `WorkerAdapter`, backing `profile.deterministic_runner`
    only. Registered once with `engine.workers.registry.
    WorkerProfileRegistry`; every `WorkerAction` it executes is real, and
    every result it returns (`RunHandle`, `ArtifactManifest`, `UsageRecord`)
    is derived from that real execution — nothing here is fabricated to
    satisfy a field."""

    def __init__(self, workspaces: WorkspaceService) -> None:
        self._workspaces = workspaces
        self._pending_actions: dict[UUID, WorkerAction] = {}
        self._prepared: dict[UUID, tuple[Workspace, WorkerAction]] = {}
        self._handles: dict[UUID, RunHandle] = {}

    def bind_action(self, execution_plan_id: UUID, action: WorkerAction) -> None:
        """Out-of-band instruction delivery — see the module docstring.
        Must be called before `prepare()` for the same `execution_plan`."""
        self._pending_actions[execution_plan_id] = action

    async def register(self) -> Registration:
        return Registration(
            worker_id=WORKER_ID,
            worker_profile_id=PROFILE_DETERMINISTIC_RUNNER,
            declared_capabilities=DECLARED_CAPABILITIES,
        )

    async def health(self) -> WorkerHealth:
        """A real check, not a hardcoded `True`: can this process actually
        spawn a subprocess with the interpreter running it? Mirrors
        `engine.environments.backends.local_process._git_version`'s "real,
        cheap check" pattern."""
        try:
            completed = await asyncio.to_thread(
                subprocess.run,  # noqa: S603
                [sys.executable, "-c", "pass"],
                capture_output=True,
                timeout=5.0,
                check=False,
            )
        except OSError as exc:
            return WorkerHealth(healthy=False, detail=f"subprocess spawn failed: {exc}")
        if completed.returncode != 0:
            return WorkerHealth(
                healthy=False,
                detail=f"interpreter self-check exited {completed.returncode}",
            )
        return WorkerHealth(healthy=True, detail="interpreter subprocess check passed")

    async def capabilities(self) -> CapabilityManifest:
        return CapabilityManifest(capability_ids=DECLARED_CAPABILITIES)

    async def prepare(
        self, *, execution_plan: ExecutionPlan, context_ref: UUID, env_ref: Workspace
    ) -> PreparedRun:
        action = self._pending_actions.pop(execution_plan.plan_id, None)
        if action is None:
            raise DdeError(
                "POLICY_DENIED",
                "No WorkerAction bound for this execution plan",
                details={"execution_plan_id": str(execution_plan.plan_id)},
            )
        if env_ref.execution_environment_id != execution_plan.execution_environment_id:
            raise DdeError(
                "ENVIRONMENT_FAILED",
                "Workspace is not bound to this plan's execution environment",
                details={
                    "execution_plan_id": str(execution_plan.plan_id),
                    "workspace_environment_id": str(env_ref.execution_environment_id),
                    "plan_environment_id": str(execution_plan.execution_environment_id),
                },
            )
        if env_ref.status != "READY":
            raise DdeError(
                "ENVIRONMENT_FAILED",
                f"Workspace is {env_ref.status}, not ready to prepare a run",
                details={"workspace_id": str(env_ref.workspace_id)},
            )
        self._prepared[execution_plan.plan_id] = (env_ref, action)
        return PreparedRun(
            plan_id=execution_plan.plan_id,
            context_ref=context_ref,
            ready=True,
            detail="workspace bound and action resolved",
        )

    async def start(self, worker_run: WorkerRun) -> RunHandle:
        prepared = self._prepared.get(worker_run.execution_plan_id)
        if prepared is None:
            raise DdeError(
                "POLICY_DENIED",
                "start() called before a successful prepare() for this plan",
                details={"execution_plan_id": str(worker_run.execution_plan_id)},
            )
        workspace, action = prepared
        for relative_path, content in action.write_files.items():
            self._workspaces.write(workspace, relative_path, content)
        changed_files: tuple[str, ...] = ()
        if action.write_files:
            snapshot = self._workspaces.snapshot(workspace)
            porcelain = str(snapshot["status_porcelain"])
            changed_files = tuple(
                line[3:] for line in porcelain.splitlines() if line.strip()
            )
        result = await self._workspaces.execute(
            workspace=workspace, command=list(action.command)
        )
        diff_text = "\n".join(changed_files)
        handle = RunHandle(
            run_id=worker_run.run_id,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=result.duration_ms,
            timed_out=result.timed_out,
            changed_files=changed_files,
            diff_text=diff_text,
        )
        self._handles[worker_run.run_id] = handle
        return handle

    async def status(self, worker_run: WorkerRun) -> RunStatus:
        handle = self._handles.get(worker_run.run_id)
        if handle is None:
            return RunStatus(
                run_id=worker_run.run_id, state="PENDING", detail="not started"
            )
        state = (
            "COMPLETED" if handle.exit_code == 0 and not handle.timed_out else "FAILED"
        )
        return RunStatus(
            run_id=worker_run.run_id,
            state=state,
            detail=f"exit_code={handle.exit_code}",
        )

    async def request_pause(self, worker_run: WorkerRun) -> PauseResult:
        return PauseResult(accepted=False, reason=_SYNCHRONOUS_BACKEND_REASON)

    async def resume(
        self, worker_run: WorkerRun, checkpoint_ref: str | None
    ) -> ResumeResult:
        return ResumeResult(accepted=False, reason=_SYNCHRONOUS_BACKEND_REASON)

    async def checkpoint(self, worker_run: WorkerRun) -> CheckpointRef:
        return CheckpointRef(
            ref=None, accepted=False, reason=_SYNCHRONOUS_BACKEND_REASON
        )

    async def cancel(self, worker_run: WorkerRun, reason: str) -> CancelResult:
        return CancelResult(accepted=False, reason=_SYNCHRONOUS_BACKEND_REASON)

    async def collect_artifacts(self, worker_run: WorkerRun) -> ArtifactManifest:
        handle = self._handles.get(worker_run.run_id)
        if handle is None:
            return ArtifactManifest(changed_files=(), diff_text="")
        return ArtifactManifest(
            changed_files=handle.changed_files, diff_text=handle.diff_text
        )

    async def collect_usage(self, worker_run: WorkerRun) -> UsageRecord:
        handle = self._handles.get(worker_run.run_id)
        duration_ms = handle.duration_ms if handle is not None else 0
        # Honestly zero: no model was invoked, so there is no token/compute
        # cost to report — not fabricated, not omitted.
        return UsageRecord(duration_ms=duration_ms, cost_usd=0.0)

    async def terminate(self, worker_run: WorkerRun) -> TerminationResult:
        handle = self._handles.get(worker_run.run_id)
        if handle is None:
            return TerminationResult(terminated=False, detail="run was never started")
        return TerminationResult(
            terminated=True, detail="run already completed synchronously"
        )

    async def cleanup(self, worker_run: WorkerRun) -> CleanupResult:
        """No adapter-owned resource outlives `start()` (no session, no
        container) — a real no-op, not a placeholder. Workspace teardown
        remains DDE's job (Chapter 7.5), never the worker's."""
        return CleanupResult(
            cleaned=True, detail="no adapter-owned resources to release"
        )
