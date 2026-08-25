"""DDE-048 Android/APK static analysis adapter (Chapter 8.1 / 9.2 / 9.3).

`start()` requires an active `capability.android_analysis` lease then runs
in-process static APK analysis. The capability is PURE_READ — no Chapter
12.4 journal. Dynamic modes refuse (see `adapters.android.static`).

Smoke: `start()` without prepare/lease is `POLICY_DENIED`.
"""

from __future__ import annotations

from uuid import UUID

from adapters.android.static import InProcessAndroidAnalyzer
from engine.capabilities.android import AndroidScanSpec
from engine.capabilities.lease_service import CapabilityLeaseService
from engine.contracts.execution_plan import ExecutionPlan
from engine.contracts.worker_run import WorkerRun
from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError
from engine.routing.policy import (
    CAPABILITY_ANDROID,
    CAPABILITY_REPOSITORY,
    CAPABILITY_TESTING,
    PROFILE_ANDROID,
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

WORKER_ID = "worker.android-static-v1"
DECLARED_CAPABILITIES = frozenset(
    {CAPABILITY_REPOSITORY, CAPABILITY_TESTING, CAPABILITY_ANDROID}
)
ANDROID_IDENTITY = ProfileIdentity(
    model_version="none",
    harness_version="android-static-v1",
    toolset_manifest="in-process.apk-static",
    image_digest="local-android",
)

_NO_PREPARE = (
    "Android adapter refuses start() without prepare() and a bound "
    "android_mode — never a fabricated successful handle"
)


class AndroidWorkerAdapter:
    def __init__(
        self,
        workspaces: WorkspaceService | None = None,
        leases: CapabilityLeaseService | None = None,
        *,
        analyzer: InProcessAndroidAnalyzer | None = None,
    ) -> None:
        self._workspaces = workspaces
        self._leases = leases
        self._analyzer = analyzer or InProcessAndroidAnalyzer()
        self._pending_actions: dict[UUID, WorkerAction] = {}
        self._prepared: dict[UUID, tuple[Workspace, WorkerAction]] = {}
        self._handles: dict[UUID, RunHandle] = {}

    def bind_action(self, execution_plan_id: UUID, action: WorkerAction) -> None:
        self._pending_actions[execution_plan_id] = action

    def profile_identity(self) -> ProfileIdentity:
        return ANDROID_IDENTITY

    async def register(self) -> Registration:
        return Registration(
            worker_id=WORKER_ID,
            worker_profile_id=PROFILE_ANDROID,
            declared_capabilities=DECLARED_CAPABILITIES,
        )

    async def health(self) -> WorkerHealth:
        return WorkerHealth(healthy=True, detail="android adapter registered")

    async def capabilities(self) -> CapabilityManifest:
        return CapabilityManifest(capability_ids=DECLARED_CAPABILITIES)

    async def prepare(
        self, *, execution_plan: ExecutionPlan, context_ref: UUID, env_ref: Workspace
    ) -> PreparedRun:
        action = self._pending_actions.pop(execution_plan.plan_id, None)
        if action is None or not action.android_mode:
            raise DdeError(
                "POLICY_DENIED",
                "AndroidWorkerAdapter requires a bound android_mode action",
                details={"execution_plan_id": str(execution_plan.plan_id)},
            )
        self._prepared[execution_plan.plan_id] = (env_ref, action)
        return PreparedRun(
            plan_id=execution_plan.plan_id,
            context_ref=context_ref,
            ready=True,
            detail="android scan bound",
        )

    async def start(self, worker_run: WorkerRun) -> RunHandle:
        prepared = self._prepared.get(worker_run.execution_plan_id)
        if prepared is None or self._leases is None:
            raise DdeError("POLICY_DENIED", _NO_PREPARE)
        workspace, action = prepared
        if not action.android_mode:
            raise DdeError("POLICY_DENIED", _NO_PREPARE)
        if not workspace.workspace_path:
            raise DdeError(
                "POLICY_DENIED",
                "android scan requires a workspace filesystem path",
                details={"workspace_id": str(workspace.workspace_id)},
            )
        await self._leases.require_active(
            tenant_id=worker_run.tenant_id,
            project_id=worker_run.project_id,
            worker_run_id=worker_run.run_id,
            capability_id=CAPABILITY_ANDROID,
        )
        result = await self._analyzer.scan(
            AndroidScanSpec(root=workspace.workspace_path, mode=action.android_mode)
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
        return PauseResult(accepted=False, reason="android scan is synchronous")

    async def resume(
        self, worker_run: WorkerRun, checkpoint_ref: str | None
    ) -> ResumeResult:
        del worker_run, checkpoint_ref
        return ResumeResult(accepted=False, reason="android scan is synchronous")

    async def checkpoint(self, worker_run: WorkerRun) -> CheckpointRef:
        del worker_run
        return CheckpointRef(
            ref=None, accepted=False, reason="android scan is synchronous"
        )

    async def cancel(self, worker_run: WorkerRun, reason: str) -> CancelResult:
        del worker_run
        return CancelResult(accepted=False, reason=reason or "android scan")

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
        self._handles.pop(worker_run.run_id, None)
        self._prepared.pop(worker_run.execution_plan_id, None)
        return TerminationResult(terminated=True, detail="android scan finished")

    async def cleanup(self, worker_run: WorkerRun) -> CleanupResult:
        return CleanupResult(cleaned=True, detail="android scan left no residue")
