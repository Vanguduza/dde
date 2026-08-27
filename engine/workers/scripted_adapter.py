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

**DDE-017 addition.** `start()` is the first real Stage 1 code path that
performs the exact side effects DDE-016's descriptor catalog names --
`capability.workspace_filesystem` (`WorkspaceService.write`),
`capability.git_operations` (`WorkspaceService.snapshot`) and
`capability.run_local_process` (`WorkspaceService.execute`) -- so it is now
the Chapter 7.2 T1 "brokered" enforcement point for all three: a
`require_active(...)` guard against a real, granted `CapabilityLease`
(`engine.capabilities.lease_service.CapabilityLeaseService`), called
immediately before each real side effect, in the same order the side
effects themselves occur. A missing, denied, expired, revoked or consumed
lease fails the run closed (`POLICY_DENIED`) rather than silently
proceeding; a lease revoked between two of these calls in the same `start()`
invocation is caught by the second call -- the real, achievable "mid-run
revocation" granularity documented in the mission summary (there is no
per-syscall interception inside a single subprocess without T2 containment,
DDE-018).

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

from engine.capabilities.lease_service import CapabilityLeaseService
from engine.capabilities.seed import side_effect_class_for
from engine.contracts.execution_plan import ExecutionPlan
from engine.contracts.worker_run import WorkerRun
from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError
from engine.environments.backends.base import CommandResult
from engine.recovery.hashing import effect_response_hash
from engine.recovery.scope import (
    LOCAL_PROCESS_SYSTEM,
    local_process_operation,
    local_process_resource,
)
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
    require_ready_workspace,
)
from engine.workers.certification import ProfileIdentity
from engine.workspaces.service import WorkspaceService

WORKER_ID = "worker.scripted-deterministic-v1"
DECLARED_CAPABILITIES = frozenset({CAPABILITY_REPOSITORY, CAPABILITY_TESTING})
SCRIPTED_IDENTITY = ProfileIdentity(
    model_version="none",
    harness_version="scripted-deterministic-v1",
    toolset_manifest="workspace.execute+write+snapshot",
    image_digest="local-process",
)

#: DDE-016's real, seeded `capability_id`s this adapter's real side effects
#: perform -- transcribed from `engine.capabilities.seed.SEED_CAPABILITIES`,
#: not re-declared independently, so the two never drift silently.
#: `capability.git_operations` is checked inside `WorkspaceService.snapshot`
#: itself (see that module), not here.
CAPABILITY_WORKSPACE_FILESYSTEM = "capability.workspace_filesystem"
CAPABILITY_RUN_LOCAL_PROCESS = "capability.run_local_process"

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

    def __init__(
        self,
        workspaces: WorkspaceService,
        leases: CapabilityLeaseService,
        *,
        worker_id: str = WORKER_ID,
        worker_profile_id: str = PROFILE_DETERMINISTIC_RUNNER,
        identity: ProfileIdentity | None = None,
    ) -> None:
        self._workspaces = workspaces
        self._leases = leases
        self._worker_id = worker_id
        self._worker_profile_id = worker_profile_id
        self._identity = identity or SCRIPTED_IDENTITY
        # DDE-020: shares the exact `ExternalEffectService` instance
        # `WorkspaceService.snapshot` itself journals `capability.
        # git_operations` through, rather than constructing a second one
        # against the same engine (see `WorkspaceService.effects`'s
        # docstring).
        self._effects = workspaces.effects
        self._pending_actions: dict[UUID, WorkerAction] = {}
        self._prepared: dict[UUID, tuple[Workspace, WorkerAction]] = {}
        self._handles: dict[UUID, RunHandle] = {}

    def bind_action(self, execution_plan_id: UUID, action: WorkerAction) -> None:
        """Out-of-band instruction delivery — see the module docstring.
        Must be called before `prepare()` for the same `execution_plan`."""
        self._pending_actions[execution_plan_id] = action

    def profile_identity(self) -> ProfileIdentity:
        return self._identity

    async def register(self) -> Registration:
        return Registration(
            worker_id=self._worker_id,
            worker_profile_id=self._worker_profile_id,
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
        require_ready_workspace(env_ref)
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
        if action.browser_url:
            raise DdeError(
                "POLICY_DENIED",
                "capability.browser probes must use PlaywrightWorkerAdapter, "
                "not ScriptedWorkerAdapter",
                details={"browser_url": action.browser_url},
            )
        if action.security_mode:
            raise DdeError(
                "POLICY_DENIED",
                "capability.security scans must use SecurityWorkerAdapter, "
                "not ScriptedWorkerAdapter",
                details={"security_mode": action.security_mode},
            )
        changed_files: tuple[str, ...] = ()
        if action.write_files:
            await self._leases.require_active(
                tenant_id=worker_run.tenant_id,
                project_id=worker_run.project_id,
                worker_run_id=worker_run.run_id,
                capability_id=CAPABILITY_WORKSPACE_FILESYSTEM,
            )
            for relative_path, content in action.write_files.items():
                self._workspaces.write(workspace, relative_path, content)
            snapshot = await self._workspaces.snapshot(
                workspace, worker_run_id=worker_run.run_id
            )
            porcelain = str(snapshot["status_porcelain"])
            changed_files = tuple(
                line[3:] for line in porcelain.splitlines() if line.strip()
            )
        lease = await self._leases.require_active(
            tenant_id=worker_run.tenant_id,
            project_id=worker_run.project_id,
            worker_run_id=worker_run.run_id,
            capability_id=CAPABILITY_RUN_LOCAL_PROCESS,
        )
        result = await self._journaled_execute(
            worker_run, workspace=workspace, lease_id=lease.lease_id, action=action
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

    async def _journaled_execute(
        self,
        worker_run: WorkerRun,
        *,
        workspace: Workspace,
        lease_id: UUID,
        action: WorkerAction,
    ) -> CommandResult:
        """DDE-020: `WorkspaceService.execute`'s real subprocess spawn
        (Chapter 7.5/DDE-010) is `capability.run_local_process`'s Chapter
        12.4 journal call site -- this adapter is the "Capability adapter"
        role (Chapter 3.8) for that capability, exactly as it already is
        `require_active`'s own T1 enforcement point (DDE-017).

        `prepare()` itself queries live `external_effects` for this
        logical scope (mission + local_process + workspace + argv) and
        refuses a new mutation while UNKNOWN/RECONCILING/SENT-abandoned or
        verified-present RECONCILED rows exist. A new WorkerRun with a new
        idempotency key still hits this gate.

        Outcome mapping: `timed_out=True` -> `mark_unknown` (Python killed
        an already-spawned process; whether its command mutated anything
        before the kill signal landed is genuinely undetermined,
        Chapter 12.3's `SIDE_EFFECT_UNKNOWN`, which
        `WorkerManagerService` also stamps on the run). Any other outcome
        is definite: `exit_code == 0` -> `mark_confirmed`; anything else
        (including a spawn-level `OSError`, reported as `exit_code=-1`
        with `timed_out=False`) -> `mark_failed`."""
        effect = await self._effects.prepare(
            tenant_id=worker_run.tenant_id,
            project_id=worker_run.project_id,
            mission_id=worker_run.mission_id,
            worker_run_id=worker_run.run_id,
            capability_lease_id=lease_id,
            target_system=LOCAL_PROCESS_SYSTEM,
            target_resource=local_process_resource(workspace),
            operation=local_process_operation(action.command),
            side_effect_class=side_effect_class_for(CAPABILITY_RUN_LOCAL_PROCESS),
            idempotency_key=f"{worker_run.run_id}:effect:{CAPABILITY_RUN_LOCAL_PROCESS}",
            evidence_ref=action.expected_artifact,
        )
        if effect.status != "PREPARED":
            # Chapter 12.5: "it never launches a second mutation." Unlike
            # `WorkspaceService.snapshot`'s read-only git commands, an
            # arbitrary caller-supplied local process is not safe to
            # blindly re-run against an already-mutated workspace -- a
            # genuine retry is a new WorkerRun (Chapter 3.10: "each
            # recovery creates a new run within the same attempt"), not a
            # second `start()` reusing this run's own idempotency key. No
            # real caller in this codebase reaches this branch today (see
            # the module docstring); it exists so the guard fails closed
            # rather than silently re-executing if one ever does.
            raise DdeError(
                "VERSION_CONFLICT",
                "capability.run_local_process was already attempted for "
                "this worker run -- refusing to repeat a non-idempotent "
                "local process invocation",
                details={"effect_id": str(effect.effect_id), "status": effect.status},
            )
        await self._effects.mark_sent(
            tenant_id=worker_run.tenant_id,
            project_id=worker_run.project_id,
            effect_id=effect.effect_id,
        )
        if action.timeout_seconds is not None:
            result = await self._workspaces.execute(
                workspace=workspace,
                command=list(action.command),
                timeout_seconds=action.timeout_seconds,
            )
        else:
            result = await self._workspaces.execute(
                workspace=workspace, command=list(action.command)
            )
        if result.timed_out:
            await self._effects.mark_unknown(
                tenant_id=worker_run.tenant_id,
                project_id=worker_run.project_id,
                effect_id=effect.effect_id,
                reason=(
                    "subprocess exceeded its timeout and was killed -- "
                    "whether its command mutated anything before the kill "
                    "signal landed cannot be determined from the exit alone"
                ),
            )
        elif result.exit_code == 0:
            await self._effects.mark_confirmed(
                tenant_id=worker_run.tenant_id,
                project_id=worker_run.project_id,
                effect_id=effect.effect_id,
                external_reference=None,
                response_hash=effect_response_hash(
                    {
                        "exit_code": result.exit_code,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                    }
                ),
            )
        else:
            await self._effects.mark_failed(
                tenant_id=worker_run.tenant_id,
                project_id=worker_run.project_id,
                effect_id=effect.effect_id,
                reason=f"exit_code={result.exit_code}",
            )
        return result

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
