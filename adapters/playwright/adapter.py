"""Playwright T1 worker adapter (DDE-043, Chapter 8.1 / 9.2 / 9.3).

`start()` is the production mutation for `capability.browser`: it calls
`CapabilityLeaseService.require_active` then journals an
EXTERNAL_NON_IDEMPOTENT effect and runs `PlaywrightBrowserProbe`.

Smoke certification uses the same fail-closed rule as the Cursor adapter:
`start()` without prepare/lease is `POLICY_DENIED`, never a fabricated
successful handle.
"""

from __future__ import annotations

from uuid import UUID

from adapters.playwright.probe import PlaywrightBrowserProbe
from engine.capabilities.browser import BrowserProbeSpec
from engine.capabilities.lease_service import CapabilityLeaseService
from engine.capabilities.seed import side_effect_class_for
from engine.contracts.execution_plan import ExecutionPlan
from engine.contracts.worker_run import WorkerRun
from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError
from engine.recovery.hashing import effect_response_hash
from engine.recovery.scope import (
    BROWSER_GOTO_OPERATION,
    BROWSER_SYSTEM,
    browser_resource,
)
from engine.routing.policy import (
    CAPABILITY_BROWSER,
    CAPABILITY_REPOSITORY,
    CAPABILITY_TESTING,
    PROFILE_VISION,
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
from engine.workers.certification import ProfileIdentity
from engine.workspaces.service import WorkspaceService

WORKER_ID = "worker.playwright-browser-v1"
CAPABILITY_BROWSER_ID = "capability.browser"
DECLARED_CAPABILITIES = frozenset(
    {CAPABILITY_REPOSITORY, CAPABILITY_TESTING, CAPABILITY_BROWSER}
)
PLAYWRIGHT_IDENTITY = ProfileIdentity(
    model_version="none",
    harness_version="playwright-browser-v1",
    toolset_manifest="playwright.chromium.goto",
    image_digest="local-playwright",
)

_NO_PREPARE = (
    "Playwright adapter refuses start() without prepare() and a bound "
    "browser probe — never a fabricated successful handle"
)


class PlaywrightWorkerAdapter:
    """Chapter 8.1 contract behind `profile.vision` for browser probes."""

    def __init__(
        self,
        workspaces: WorkspaceService | None = None,
        leases: CapabilityLeaseService | None = None,
        *,
        probe: PlaywrightBrowserProbe | None = None,
    ) -> None:
        self._workspaces = workspaces
        self._leases = leases
        self._probe = probe or PlaywrightBrowserProbe()
        self._pending_actions: dict[UUID, WorkerAction] = {}
        self._prepared: dict[UUID, tuple[Workspace, WorkerAction]] = {}
        self._handles: dict[UUID, RunHandle] = {}

    def bind_action(self, execution_plan_id: UUID, action: WorkerAction) -> None:
        self._pending_actions[execution_plan_id] = action

    def profile_identity(self) -> ProfileIdentity:
        return PLAYWRIGHT_IDENTITY

    async def register(self) -> Registration:
        return Registration(
            worker_id=WORKER_ID,
            worker_profile_id=PROFILE_VISION,
            declared_capabilities=DECLARED_CAPABILITIES,
        )

    async def health(self) -> WorkerHealth:
        return WorkerHealth(
            healthy=True,
            detail="playwright adapter registered (runtime checked at probe)",
        )

    async def capabilities(self) -> CapabilityManifest:
        return CapabilityManifest(capability_ids=DECLARED_CAPABILITIES)

    async def prepare(
        self, *, execution_plan: ExecutionPlan, context_ref: UUID, env_ref: Workspace
    ) -> PreparedRun:
        action = self._pending_actions.pop(execution_plan.plan_id, None)
        if action is None or not action.browser_url:
            raise DdeError(
                "POLICY_DENIED",
                "PlaywrightWorkerAdapter requires a bound browser_url action",
                details={"execution_plan_id": str(execution_plan.plan_id)},
            )
        self._prepared[execution_plan.plan_id] = (env_ref, action)
        return PreparedRun(
            plan_id=execution_plan.plan_id,
            context_ref=context_ref,
            ready=True,
            detail="browser probe bound",
        )

    async def start(self, worker_run: WorkerRun) -> RunHandle:
        prepared = self._prepared.get(worker_run.execution_plan_id)
        if prepared is None or self._leases is None:
            raise DdeError("POLICY_DENIED", _NO_PREPARE)
        _workspace, action = prepared
        if not action.browser_url:
            raise DdeError("POLICY_DENIED", _NO_PREPARE)

        lease = await self._leases.require_active(
            tenant_id=worker_run.tenant_id,
            project_id=worker_run.project_id,
            worker_run_id=worker_run.run_id,
            capability_id=CAPABILITY_BROWSER_ID,
        )
        effects = None if self._workspaces is None else self._workspaces.effects
        effect_id = None
        if effects is not None:
            effect = await effects.prepare(
                tenant_id=worker_run.tenant_id,
                project_id=worker_run.project_id,
                mission_id=worker_run.mission_id,
                worker_run_id=worker_run.run_id,
                capability_lease_id=lease.lease_id,
                target_system=BROWSER_SYSTEM,
                target_resource=browser_resource(action.browser_url),
                operation=BROWSER_GOTO_OPERATION,
                side_effect_class=side_effect_class_for(CAPABILITY_BROWSER_ID),
                idempotency_key=f"{worker_run.run_id}:effect:{CAPABILITY_BROWSER_ID}",
                evidence_ref=action.browser_url,
            )
            if effect.status != "PREPARED":
                raise DdeError(
                    "VERSION_CONFLICT",
                    "capability.browser was already attempted for this "
                    "worker run — refusing to blind-retry an "
                    "EXTERNAL_NON_IDEMPOTENT probe",
                    details={
                        "effect_id": str(effect.effect_id),
                        "status": effect.status,
                    },
                )
            await effects.mark_sent(
                tenant_id=worker_run.tenant_id,
                project_id=worker_run.project_id,
                effect_id=effect.effect_id,
            )
            effect_id = effect.effect_id

        result = await self._probe.probe(
            BrowserProbeSpec(
                url=action.browser_url,
                expect_text=action.browser_expect_text,
            )
        )
        if effects is not None and effect_id is not None:
            if result.timed_out:
                await effects.mark_unknown(
                    tenant_id=worker_run.tenant_id,
                    project_id=worker_run.project_id,
                    effect_id=effect_id,
                    reason="playwright navigation timed out",
                )
            elif result.exit_code == 0:
                await effects.mark_confirmed(
                    tenant_id=worker_run.tenant_id,
                    project_id=worker_run.project_id,
                    effect_id=effect_id,
                    external_reference=action.browser_url,
                    response_hash=effect_response_hash(
                        {
                            "exit_code": result.exit_code,
                            "stdout": result.stdout,
                            "stderr": result.stderr,
                        }
                    ),
                )
            else:
                await effects.mark_failed(
                    tenant_id=worker_run.tenant_id,
                    project_id=worker_run.project_id,
                    effect_id=effect_id,
                    reason=result.stderr or f"exit_code={result.exit_code}",
                )

        handle = RunHandle(
            run_id=worker_run.run_id,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=result.duration_ms,
            timed_out=result.timed_out,
            changed_files=(),
            diff_text="",
        )
        self._handles[worker_run.run_id] = handle
        return handle

    async def status(self, worker_run: WorkerRun) -> RunStatus:
        handle = self._handles.get(worker_run.run_id)
        if handle is None:
            return RunStatus(run_id=worker_run.run_id, state="unknown", detail="")
        state = "COMPLETED" if handle.exit_code == 0 else "FAILED"
        return RunStatus(run_id=worker_run.run_id, state=state, detail=handle.stderr)

    async def request_pause(self, worker_run: WorkerRun) -> PauseResult:
        del worker_run
        return PauseResult(accepted=False, reason="browser probe is synchronous")

    async def resume(
        self, worker_run: WorkerRun, checkpoint_ref: str | None
    ) -> ResumeResult:
        del worker_run, checkpoint_ref
        return ResumeResult(accepted=False, reason="browser probe is synchronous")

    async def checkpoint(self, worker_run: WorkerRun) -> CheckpointRef:
        del worker_run
        return CheckpointRef(
            ref=None, accepted=False, reason="browser probe is synchronous"
        )

    async def cancel(self, worker_run: WorkerRun, reason: str) -> CancelResult:
        del worker_run
        return CancelResult(accepted=False, reason=reason or "browser probe")

    async def collect_artifacts(self, worker_run: WorkerRun) -> ArtifactManifest:
        handle = self._handles.get(worker_run.run_id)
        return ArtifactManifest(
            changed_files=() if handle is None else handle.changed_files,
            diff_text="" if handle is None else handle.diff_text,
        )

    async def collect_usage(self, worker_run: WorkerRun) -> UsageRecord:
        handle = self._handles.get(worker_run.run_id)
        return UsageRecord(
            duration_ms=0 if handle is None else handle.duration_ms, cost_usd=0.0
        )

    async def terminate(self, worker_run: WorkerRun) -> TerminationResult:
        del worker_run
        return TerminationResult(terminated=True, detail="browser probe finished")

    async def cleanup(self, worker_run: WorkerRun) -> CleanupResult:
        self._handles.pop(worker_run.run_id, None)
        return CleanupResult(cleaned=True, detail="browser probe handles cleared")
