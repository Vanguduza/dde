"""Claude Code worker adapter (EDR-0001 Path A).

`docs/truth/edr/EDR-0001-subscription-based-worker-credentials.md` is the
design and research this module implements. Its "Recommendation" section
picks Path A -- a subprocess-only adapter with a mandatory, per-invocation,
non-standing human approval gate and no broker/credential involvement at
all -- as the smallest safe next step, deferring Path B (a
`DelegatedSessionProvider`/broker credential-holding design) until Open
Questions #1/#2 there are answered. This module builds Path A only.

**Why this adapter never touches an Anthropic credential.** A Claude Code
Pro/Max subscription seat is a human's own out-of-band-obtained,
non-DDE-mintable, hard-to-revoke entitlement (EDR-0001's "Context"
section) -- none of Chapter 14.3's five credential-broker tiers describe
it, and AGENTS.md forbids "passing a long-lived credential to anything
that executes model-generated code." This adapter resolves that not by
custody-with-discipline but by construction: it never reads, stores or
receives any Anthropic credential at all. It spawns the human's own
already-`claude login`-authenticated local CLI as a real subprocess --
mirroring `engine.workers.scripted_adapter.ScriptedWorkerAdapter`'s
already-proven "real subprocess behind a real, checked gate" pattern -- and
lets the OS-level, already-authenticated `claude` process authenticate
itself exactly as it would for a human typing at a terminal. EDR-0001's
Research Finding 2 confirms automating the real, unmodified `claude`
binary this way is Anthropic's own documented, endorsed pattern; extracting
or relaying its credential to anything else is what Anthropic's February
2026 clarification prohibits, and this adapter is built so it structurally
cannot do that (see the class docstring's explicit negative constraint).

**Why the gate is `ApprovalService`, not `CapabilityLeaseService`.**
Mirroring `adapters/cursor/adapter.py`'s already-established "fail-closed
policy shell" pattern, this adapter substitutes `engine.governance.
service.ApprovalService.require_approved` for `ScriptedWorkerAdapter`'s
`CapabilityLeaseService.require_active` as its production mutation gate
(`start()`): the resource being protected is a human's personal,
rate-limited, ToS-bounded subscription seat, not a workspace-scoped
capability lease, and the human's explicit instruction ("a human manually
approve every piece of work routed to Claude Code") requires a fresh,
individually-decided approval per invocation -- never a batch/standing
pre-authorization. `external_model_invocation` (`engine.governance.types.
APPROVAL_TYPES`) is in `STANDING_FORBIDDEN_TYPES` for exactly this reason;
see that module for the enforcement mechanism this adapter relies on
(`ApprovalService.grant_standing`/`authorize_standing` reject the type
outright).

**Honest gap, not a blocker.** The exact non-interactive prompt flag this
module defaults to (`claude -p "<prompt>"`) is EDR-0001 Research Finding 1's
best-documented shape as of 2026-08-21, not something this mission
independently re-verified against a live `claude` binary. Both the binary
name and its argv are constructor parameters (`ClaudePromptBinding.binary`/
`args`), not hardcoded elsewhere in this module, so a wrong guess is a
one-line caller-side fix, never a change to this adapter's approval-gating
or subprocess-capture logic.
"""

from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass
from uuid import UUID

from engine.contracts.execution_plan import ExecutionPlan
from engine.contracts.worker_run import WorkerRun
from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError
from engine.governance.hashing import approval_scope_hash
from engine.governance.service import ApprovalService
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
    WorkerHealth,
    require_ready_workspace,
)
from engine.workers.certification import ProfileIdentity
from engine.workspaces.service import WorkspaceService

WORKER_ID = "worker.claude-code-v1"

#: Deliberately NOT one of `engine.routing.policy`'s Chapter 6.2 declared
#: profile ids -- Claude Code has no chartered `workload_classes` entry yet
#: (out of this mission's scope; wiring routing to prefer/require it is a
#: separate, later decision). Kept local to this adapter so registering it
#: with a shared `engine.workers.registry.WorkerProfileRegistry` (keyed by
#: `worker_profile_id`) can never silently collide with -- and overwrite --
#: `adapters.cursor.adapter.CursorWorkerAdapter`'s own
#: `profile.general_implementation` registration.
WORKER_PROFILE_ID = "profile.claude_code_cli"

#: `engine.capabilities.seed.SEED_CAPABILITIES`'s real, seeded
#: `capability_id` this adapter's one real side effect performs --
#: transcribed from that module, not re-declared independently.
CAPABILITY_CLAUDE_CODE_INVOKE = "capability.claude_code_invoke"

#: Must match the literal added to `engine.governance.types.APPROVAL_TYPES`
#: and `STANDING_FORBIDDEN_TYPES` for EDR-0001 Path A. Duplicated here
#: (rather than imported as a single named constant) because `types.py`
#: declares it only as a member of two frozensets, not as its own exported
#: name; `tests/unit/test_claude_adapter_requires_approval.py` asserts this
#: exact string is a member of both sets so the two call sites cannot drift
#: silently.
APPROVAL_TYPE_EXTERNAL_MODEL_INVOCATION = "external_model_invocation"

DEFAULT_BINARY = "claude"
#: Anthropic's documented non-interactive prompt flag (EDR-0001 Research
#: Finding 1: "`claude -p "<prompt>"`" / Finding 3's "`claude -p ...`").
#: See the module docstring's honest-gap note.
DEFAULT_ARGS: tuple[str, ...] = ("-p",)
#: EDR-0001 Research Finding 3: a live session window is measured in hours
#: (a rolling 5-hour window), not the shorter timeouts appropriate for a
#: purely local, deterministic command -- `ScriptedWorkerAdapter`'s own
#: `DEFAULT_EXECUTE_TIMEOUT_SECONDS` (60s) would be a false timeout here.
DEFAULT_TIMEOUT_SECONDS = 60.0 * 30

CLAUDE_IDENTITY = ProfileIdentity(
    model_version="unspecified",
    harness_version="claude-code-adapter-subprocess-v1",
    toolset_manifest="claude-cli;credential_custody=none",
    image_digest="unspecified",
)

_NO_PROMPT_BOUND = (
    "No prompt bound for this execution plan -- bind_prompt() must be "
    "called before prepare()"
)
_SYNCHRONOUS_BACKEND_REASON = (
    "ClaudeCodeWorkerAdapter executes its invocation synchronously inside "
    "start() and returns only once terminal; there is no in-flight window "
    "for a mid-run control operation to act on."
)


@dataclass(frozen=True)
class ClaudePromptBinding:
    """The out-of-band instruction this adapter needs. Chapter 8.1's
    `prepare(execution_plan, context_ref, env_ref)` has no slot for "what
    to do" -- mirroring `engine.workers.scripted_adapter`'s own
    `WorkerAction`/`bind_action` addition (see that module's docstring),
    this is delivered out-of-band via `bind_prompt()` instead.

    `binary`/`args` default to the real `claude` CLI's documented
    non-interactive shape but are per-binding overrides specifically so a
    test can point this adapter at a fake double instead of the real
    executable (see `tests/unit/test_claude_adapter_requires_approval.py`)
    without changing this module's production defaults.
    """

    prompt: str
    binary: str = DEFAULT_BINARY
    args: tuple[str, ...] = DEFAULT_ARGS
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS


def claude_invocation_scope_hash(
    *, mission_id: UUID, execution_plan_id: UUID, binding: ClaudePromptBinding
) -> str:
    """Chapter 13.1 identity of the *exact* thing an `Approval` binds to
    (`engine.governance.hashing.approval_scope_hash`). Exported as a public,
    module-level function -- not a private adapter method -- so the caller
    that requests/decides an approval before this run's `start()` executes
    (which happens before a `WorkerRun` row exists, per Chapter 3.9 step 10)
    can compute the identical hash from the same
    `(mission_id, execution_plan_id, prompt, binary, args)` tuple without
    reaching into adapter internals or risking the two computations
    drifting apart. A re-planned prompt produces a different hash and
    cannot consume a prior approval, by `approval_scope_hash`'s own
    construction (Chapter 13.1: "Approval cannot be reused for a
    materially different plan")."""
    return approval_scope_hash(
        approval_type=APPROVAL_TYPE_EXTERNAL_MODEL_INVOCATION,
        mission_id=mission_id,
        payload={
            "execution_plan_id": str(execution_plan_id),
            "prompt": binding.prompt,
            "binary": binding.binary,
            "args": list(binding.args),
        },
    )


class ClaudeCodeWorkerAdapter:
    """Chapter 8.1's `WorkerAdapter`, behind the adapter-local
    `profile.claude_code_cli` -- see module docstring for why this is not
    one of Chapter 6.2's declared routing profiles yet.

    **What this adapter must never do** (EDR-0001 Research Finding 2 point
    3, transcribed as an explicit, checkable constraint, not an
    assumption): read `~/.claude/.credentials.json` or any OS keychain
    entry Claude Code uses; read, set or forward `CLAUDE_CODE_OAUTH_TOKEN`,
    `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` from any value DDE itself
    captured or derived; or call any Anthropic API endpoint directly. Its
    only supported interaction with Anthropic is spawning the unmodified
    `claude` executable and reading its stdout/stderr/exit code -- the
    subprocess this module spawns is never given an explicit `env=`
    override, so it inherits this process's environment completely
    unmodified and authenticates exactly as the human's own terminal
    session already does. A future edit that adds any credential read,
    env-var forwarding, or direct Anthropic API call here reverts this
    adapter to the prohibited "third-party harness relaying subscription
    credentials" pattern the EDR's research found Anthropic explicitly
    bans -- do not add one.
    """

    def __init__(
        self,
        workspaces: WorkspaceService,
        approvals: ApprovalService,
        *,
        worker_id: str = WORKER_ID,
        worker_profile_id: str = WORKER_PROFILE_ID,
        identity: ProfileIdentity | None = None,
    ) -> None:
        self._workspaces = workspaces
        self._approvals = approvals
        self._worker_id = worker_id
        self._worker_profile_id = worker_profile_id
        self._identity = identity or CLAUDE_IDENTITY
        self._pending_prompts: dict[UUID, ClaudePromptBinding] = {}
        self._prepared: dict[UUID, tuple[Workspace, ClaudePromptBinding]] = {}
        self._handles: dict[UUID, RunHandle] = {}
        # EDR-0001 Research Finding 3 / Open Question #3: a subscription
        # seat's headless/scripted quota is smaller than, and shared with,
        # the human's own interactive use -- at most one live invocation
        # runs at a time. A second concurrent start() queues behind this
        # lock rather than running in parallel; this is enforced inside the
        # adapter itself, not deferred to routing (per the EDR's own
        # recommendation).
        self._invocation_lock = asyncio.Lock()

    def bind_prompt(
        self, execution_plan_id: UUID, binding: ClaudePromptBinding
    ) -> None:
        """Out-of-band instruction delivery -- see `ClaudePromptBinding`'s
        docstring. Must be called before `prepare()` for the same
        `execution_plan`."""
        self._pending_prompts[execution_plan_id] = binding

    def profile_identity(self) -> ProfileIdentity:
        return self._identity

    async def register(self) -> Registration:
        return Registration(
            worker_id=self._worker_id,
            worker_profile_id=self._worker_profile_id,
            declared_capabilities=frozenset({CAPABILITY_CLAUDE_CODE_INVOKE}),
        )

    async def health(self) -> WorkerHealth:
        """A real, cheap check that the configured binary exists and runs
        (mirrors `ScriptedWorkerAdapter.health()`'s own "real check, not a
        hardcoded True" pattern) -- never a live-session check, which would
        require touching credential state this adapter forbids itself from
        reading. A stale/expired session is discovered only by a real
        invocation failing, surfaced as a normal run failure, never
        specially inspected in advance."""
        try:
            completed = await asyncio.to_thread(
                subprocess.run,  # noqa: S603
                [DEFAULT_BINARY, "--version"],
                capture_output=True,
                timeout=10.0,
                check=False,
            )
        except OSError as exc:
            return WorkerHealth(
                healthy=False,
                detail=f"'{DEFAULT_BINARY}' subprocess spawn failed: {exc}",
            )
        if completed.returncode != 0:
            return WorkerHealth(
                healthy=False,
                detail=f"'{DEFAULT_BINARY} --version' exited {completed.returncode}",
            )
        return WorkerHealth(healthy=True, detail="claude CLI subprocess check passed")

    async def capabilities(self) -> CapabilityManifest:
        return CapabilityManifest(
            capability_ids=frozenset({CAPABILITY_CLAUDE_CODE_INVOKE})
        )

    async def prepare(
        self, *, execution_plan: ExecutionPlan, context_ref: UUID, env_ref: Workspace
    ) -> PreparedRun:
        binding = self._pending_prompts.pop(execution_plan.plan_id, None)
        if binding is None:
            raise DdeError(
                "POLICY_DENIED",
                _NO_PROMPT_BOUND,
                details={"execution_plan_id": str(execution_plan.plan_id)},
            )
        require_ready_workspace(env_ref)
        self._prepared[execution_plan.plan_id] = (env_ref, binding)
        return PreparedRun(
            plan_id=execution_plan.plan_id,
            context_ref=context_ref,
            ready=True,
            detail="workspace bound; live invocation still needs a human approval",
        )

    async def start(self, worker_run: WorkerRun) -> RunHandle:
        prepared = self._prepared.get(worker_run.execution_plan_id)
        if prepared is None:
            raise DdeError(
                "POLICY_DENIED",
                "start() called before a successful prepare() for this plan",
                details={"execution_plan_id": str(worker_run.execution_plan_id)},
            )
        workspace, binding = prepared
        scope_hash = claude_invocation_scope_hash(
            mission_id=worker_run.mission_id,
            execution_plan_id=worker_run.execution_plan_id,
            binding=binding,
        )
        # Mandatory, non-standing human approval gate -- the one production
        # mutation call site enforcing EDR-0001 Path A's chartered rule
        # ("every single invocation requires its own human decide() call").
        # `require_approved` itself raises a typed `POLICY_DENIED` and
        # returns without a value when no fresh, individually-decided,
        # unexpired Approval bound to this exact scope_hash exists -- no
        # `claude` process is ever spawned on that path.
        await self._approvals.require_approved(
            tenant_id=worker_run.tenant_id,
            project_id=worker_run.project_id,
            scope_hash=scope_hash,
            approval_type=APPROVAL_TYPE_EXTERNAL_MODEL_INVOCATION,
        )
        async with self._invocation_lock:
            command = [binding.binary, *binding.args, binding.prompt]
            result = await self._workspaces.execute(
                workspace=workspace,
                command=command,
                timeout_seconds=binding.timeout_seconds,
            )
        handle = RunHandle(
            run_id=worker_run.run_id,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=result.duration_ms,
            timed_out=result.timed_out,
            # Unlike `ScriptedWorkerAdapter`, this adapter does not
            # additionally acquire a `capability.git_operations` lease to
            # snapshot changed files after the invocation -- EDR-0001 Path
            # A scopes this adapter to the approval gate and the subprocess
            # call only. Left honestly empty rather than fabricated; a
            # caller wanting a diff can run its own snapshot.
            changed_files=(),
            diff_text="",
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
        del worker_run
        return PauseResult(accepted=False, reason=_SYNCHRONOUS_BACKEND_REASON)

    async def resume(
        self, worker_run: WorkerRun, checkpoint_ref: str | None
    ) -> ResumeResult:
        del worker_run, checkpoint_ref
        return ResumeResult(accepted=False, reason=_SYNCHRONOUS_BACKEND_REASON)

    async def checkpoint(self, worker_run: WorkerRun) -> CheckpointRef:
        del worker_run
        return CheckpointRef(
            ref=None, accepted=False, reason=_SYNCHRONOUS_BACKEND_REASON
        )

    async def cancel(self, worker_run: WorkerRun, reason: str) -> CancelResult:
        del worker_run
        return CancelResult(
            accepted=False, reason=reason or _SYNCHRONOUS_BACKEND_REASON
        )

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
        # EDR-0001 Research Finding 3: DDE has no visibility into which of
        # the human's usage pools a subscription-metered invocation drew
        # from or how much it consumed. Honestly zero, mirroring
        # `ScriptedWorkerAdapter.collect_usage`'s own convention -- not
        # fabricated, not omitted.
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
        container, and -- by this adapter's whole design -- no credential
        of any kind). Workspace teardown remains DDE's job (Chapter 7.5),
        never the worker's."""
        del worker_run
        return CleanupResult(
            cleaned=True, detail="no adapter-owned resources to release"
        )
