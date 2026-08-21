"""Cursor T2 worker adapter (DDE-025, Appendix A).

Vendor SDKs may be imported only from `adapters/cursor/**` (AGENTS.md).
This mission does not import `cursor_sdk`: a live model invocation would
require a brokered credential (Chapter 14.3) and would put an API key on
a path this adapter is forbidden to take (`auto_create_pr` is forbidden;
the key must never enter the ExecutionEnvironment).

`start()` fail-closes with `POLICY_DENIED` rather than fabricating a
successful `RunHandle`. Smoke certification therefore proves the policy
shell, not a hosted-model call.
"""

from __future__ import annotations

from uuid import UUID

from engine.contracts.execution_plan import ExecutionPlan
from engine.contracts.worker_run import WorkerRun
from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError
from engine.routing.policy import (
    CAPABILITY_REPOSITORY,
    CAPABILITY_TESTING,
    PROFILE_GENERAL_IMPLEMENTATION,
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
    WorkerHealth,
)
from engine.workers.certification import ProfileIdentity

WORKER_ID = "worker.cursor-t2-v1"
AUTO_CREATE_PR = False
CURSOR_IDENTITY = ProfileIdentity(
    model_version="unspecified",
    harness_version="cursor-adapter-policy-shell-v1",
    toolset_manifest="t2-harness;auto_create_pr=forbidden",
    image_digest="unspecified",
)
_NO_LIVE_INVOCATION = (
    "Cursor adapter refuses a live model invocation without a brokered "
    "credential; cursor_sdk is not imported on this path"
)


class CursorWorkerAdapter:
    """Chapter 8.1 contract behind `profile.general_implementation`."""

    def profile_identity(self) -> ProfileIdentity:
        return CURSOR_IDENTITY

    async def register(self) -> Registration:
        if AUTO_CREATE_PR:
            raise DdeError(
                "POLICY_DENIED",
                "auto_create_pr is forbidden on the Cursor adapter",
                retryable=False,
            )
        return Registration(
            worker_id=WORKER_ID,
            worker_profile_id=PROFILE_GENERAL_IMPLEMENTATION,
            declared_capabilities=frozenset(
                {CAPABILITY_REPOSITORY, CAPABILITY_TESTING}
            ),
        )

    async def health(self) -> WorkerHealth:
        return WorkerHealth(
            healthy=True,
            detail="policy shell ready; live cursor-sdk invocation is not certified",
        )

    async def capabilities(self) -> CapabilityManifest:
        return CapabilityManifest(
            capability_ids=frozenset({CAPABILITY_REPOSITORY, CAPABILITY_TESTING})
        )

    async def prepare(
        self, *, execution_plan: ExecutionPlan, context_ref: UUID, env_ref: Workspace
    ) -> PreparedRun:
        if env_ref.execution_environment_id != execution_plan.execution_environment_id:
            raise DdeError(
                "ENVIRONMENT_FAILED",
                "Workspace is not bound to this plan's execution environment",
                details={
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
        return PreparedRun(
            plan_id=execution_plan.plan_id,
            context_ref=context_ref,
            ready=True,
            detail="workspace bound; live invocation still needs a credential",
        )

    async def start(self, worker_run: WorkerRun) -> RunHandle:
        raise DdeError(
            "POLICY_DENIED",
            _NO_LIVE_INVOCATION,
            retryable=False,
            details={
                "run_id": str(worker_run.run_id),
                "auto_create_pr": AUTO_CREATE_PR,
            },
        )

    async def status(self, worker_run: WorkerRun) -> RunStatus:
        return RunStatus(
            run_id=worker_run.run_id,
            state="PENDING",
            detail="no live invocation",
        )

    async def request_pause(self, worker_run: WorkerRun) -> PauseResult:
        del worker_run
        return PauseResult(accepted=False, reason=_NO_LIVE_INVOCATION)

    async def resume(
        self, worker_run: WorkerRun, checkpoint_ref: str | None
    ) -> ResumeResult:
        del worker_run, checkpoint_ref
        return ResumeResult(accepted=False, reason=_NO_LIVE_INVOCATION)

    async def checkpoint(self, worker_run: WorkerRun) -> CheckpointRef:
        del worker_run
        return CheckpointRef(ref=None, accepted=False, reason=_NO_LIVE_INVOCATION)

    async def cancel(self, worker_run: WorkerRun, reason: str) -> CancelResult:
        del worker_run
        return CancelResult(accepted=False, reason=reason or _NO_LIVE_INVOCATION)

    async def collect_artifacts(self, worker_run: WorkerRun) -> ArtifactManifest:
        del worker_run
        return ArtifactManifest(changed_files=(), diff_text="")

    async def collect_usage(self, worker_run: WorkerRun) -> UsageRecord:
        del worker_run
        return UsageRecord(duration_ms=0, cost_usd=0.0)

    async def terminate(self, worker_run: WorkerRun) -> TerminationResult:
        del worker_run
        return TerminationResult(terminated=False, detail="no live invocation")

    async def cleanup(self, worker_run: WorkerRun) -> CleanupResult:
        del worker_run
        return CleanupResult(
            cleaned=True, detail="no adapter-owned resources to release"
        )
