"""Execute DDE-069 candidate verification requests through DDE-068 authority.

Frontend Studio owns request/candidate lifecycle only. The actual verdict remains
an ordinary `engine.verification.VerificationRun` with ordinary Evidence rows,
executed by `VerificationRunnerService`. No WorkerRun is fabricated for a human
or Inspector edit.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.capabilities.android import AndroidCapability
from engine.capabilities.browser import BrowserCapability
from engine.capabilities.database import DatabaseCapability
from engine.capabilities.lease_service import CapabilityLeaseService
from engine.capabilities.security import SecurityCapability
from engine.capabilities.visual_critic import VisualCriticCapability
from engine.contracts.acceptance_oracle import AcceptanceOracle
from engine.contracts.frontend_candidate import FrontendCandidate
from engine.contracts.frontend_verification_request import FrontendVerificationRequest
from engine.contracts.task import Task
from engine.contracts.verification_run import VerificationRun
from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError
from engine.events.service import EventService
from engine.fabric.lifecycle import FabricLifecycleService
from engine.missions.attempts import TaskAttemptService
from engine.missions.service import MissionService
from engine.studio.candidates.lifecycle import CandidateState
from engine.studio.candidates.service import CandidateService
from engine.studio.preview_runtime.service import PreviewService, PreviewState
from engine.studio.verification_requests import CandidateVerificationRequestService
from engine.truth.db import open_unit_of_work
from engine.verification.capability_runtime import (
    CAPABILITY_BROWSER,
    CAPABILITY_VISUAL_CRITIQUE,
    LeaseBoundBrowserCapability,
    LeaseBoundVisualCriticCapability,
)
from engine.verification.repository import AcceptanceOracleRepository
from engine.verification.runner import VerificationRunnerService
from engine.workspaces.paths import resolve_within_workspace
from engine.workspaces.service import WorkspaceService

_BROWSER_KINDS = frozenset(
    {"api_probe", "visual_diff", "silhouette", "visual_critique"}
)
_UNSUPPORTED_DEFAULT_KINDS = frozenset(
    {"security_scan", "android_scan", "db_assertion"}
)


@dataclass(frozen=True)
class CandidateVerificationExecution:
    request: FrontendVerificationRequest
    run: VerificationRun | None
    candidate: FrontendCandidate


class CandidateVerificationExecutionService:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        requests: CandidateVerificationRequestService | None = None,
        previews: PreviewService | None = None,
        candidates: CandidateService | None = None,
        workspaces: WorkspaceService | None = None,
        missions: MissionService | None = None,
        attempts: TaskAttemptService | None = None,
        leases: CapabilityLeaseService | None = None,
        browser_factory: Callable[[], BrowserCapability] | None = None,
        visual_critic_factory: Callable[[], VisualCriticCapability] | None = None,
        security: SecurityCapability | None = None,
        android: AndroidCapability | None = None,
        database: DatabaseCapability | None = None,
        runner_factory: Callable[..., VerificationRunnerService] | None = None,
        lifecycle: FabricLifecycleService | None = None,
    ) -> None:
        self._engine = engine
        self._workspaces = workspaces or WorkspaceService(engine)
        self._candidates = candidates or CandidateService(engine)
        self._previews = previews or PreviewService(engine, workspaces=self._workspaces)
        self._requests = requests or CandidateVerificationRequestService(engine)
        events = EventService(engine)
        self._missions = missions or MissionService(engine, events)
        self._attempts = attempts or TaskAttemptService(engine, events=events)
        self._leases = leases or CapabilityLeaseService(engine, events=events)
        self._oracles = AcceptanceOracleRepository()
        self._browser_factory = browser_factory or _default_browser
        self._visual_critic_factory = visual_critic_factory or _default_visual_critic
        self._security = security
        self._android = android
        self._database = database
        self._runner_factory = runner_factory or VerificationRunnerService
        self._lifecycle = lifecycle or FabricLifecycleService(engine)

    async def execute(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        verification_request_id: UUID,
    ) -> CandidateVerificationExecution:
        request = await self._requests.get(
            tenant_id=tenant_id,
            project_id=project_id,
            verification_request_id=verification_request_id,
        )
        if request.mission_id != mission_id:
            raise DdeError(
                "POLICY_DENIED",
                "verification request is not bound to the command mission",
                retryable=False,
                details={"verification_request_id": str(verification_request_id)},
            )
        if request.state != "PENDING":
            raise DdeError(
                "VERSION_CONFLICT",
                f"verification request is {request.state}, not PENDING",
                retryable=request.state == "RUNNING",
                details={"verification_request_id": str(verification_request_id)},
            )

        try:
            context = await self._resolve_context(
                tenant_id=tenant_id, project_id=project_id, request=request
            )
        except DdeError as exc:
            return await self._block_before_run(request, exc)

        request = await self._requests.mark_running(
            tenant_id=tenant_id,
            project_id=project_id,
            verification_request_id=verification_request_id,
        )
        try:
            candidate = await self._candidates.transition(
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=request.candidate_id,
                target=CandidateState.VERIFYING,
                detail="DDE-068 verification executing for current LIVE preview",
            )
        except DdeError as exc:
            await self._requests.mark_blocked(
                tenant_id=tenant_id,
                project_id=project_id,
                verification_request_id=verification_request_id,
                reason=f"candidate could not enter VERIFYING: {exc}",
            )
            raise

        await self._lifecycle.emit(
            tenant_id=tenant_id,
            project_id=project_id,
            event_kind="BEFORE_VERIFICATION",
            context={
                "mission_id": str(mission_id),
                "verification_request_id": str(verification_request_id),
                "candidate_id": str(request.candidate_id),
                "content_hash": request.content_hash,
            },
        )
        try:
            browser, critic = await self._capabilities(
                tenant_id=tenant_id,
                project_id=project_id,
                request=request,
                task=context.task,
                execution_plan_id=context.execution_plan_id,
                oracle_kinds=context.oracle_kinds,
            )
            runner = self._runner_factory(
                self._engine,
                self._workspaces,
                browser=browser,
                visual_critic=critic,
                security=self._security,
                android=self._android,
                database=self._database,
            )
            run = await runner.run_workspace_revision(
                task=context.task,
                workspace=context.workspace,
                oracle=context.oracle,
                subject_kind="FRONTEND_CANDIDATE",
                subject_id=request.candidate_id,
                revision_fingerprint=context.revision_fingerprint,
                render_url_override=context.render_url,
                idempotency_key=(
                    f"frontend-candidate-verification:{verification_request_id}:"
                    f"{context.revision_fingerprint}"
                ),
            )
        except DdeError as exc:
            blocked = await self._requests.mark_blocked(
                tenant_id=tenant_id,
                project_id=project_id,
                verification_request_id=verification_request_id,
                reason=f"verification execution blocked: {exc}",
            )
            latest = await self._candidates.get(
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=request.candidate_id,
            )
            if CandidateState(latest.state) is CandidateState.VERIFYING:
                latest = await self._candidates.transition(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    candidate_id=request.candidate_id,
                    target=CandidateState.BLOCKED,
                    detail=blocked.reason,
                )
            await self._lifecycle.emit(
                tenant_id=tenant_id,
                project_id=project_id,
                event_kind="AFTER_VERIFICATION",
                context={
                    "verification_request_id": str(verification_request_id),
                    "candidate_id": str(request.candidate_id),
                    "state": "BLOCKED",
                    "reason": blocked.reason,
                },
            )
            return CandidateVerificationExecution(blocked, None, latest)

        terminal = "PASSED" if run.status == "PASSED" else "FAILED"
        terminal_request = await self._requests.record_run(
            tenant_id=tenant_id,
            project_id=project_id,
            verification_request_id=verification_request_id,
            verification_run_id=run.verification_run_id,
            terminal_state=terminal,
            reason=(
                "DDE-068 verification passed"
                if terminal == "PASSED"
                else f"DDE-068 verification ended {run.status}"
            ),
        )
        if terminal_request.state == "SUPERSEDED":
            # A concurrent mutation owns candidate state now. The completed run is
            # preserved on the request for audit but cannot become current evidence.
            latest = await self._candidates.get(
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=request.candidate_id,
            )
            await self._emit_after_verification(
                tenant_id=tenant_id,
                project_id=project_id,
                request=terminal_request,
                run=run,
                candidate=latest,
            )
            return CandidateVerificationExecution(terminal_request, run, latest)

        target = (
            CandidateState.VERIFIED if terminal == "PASSED" else CandidateState.FAILED
        )
        latest = await self._candidates.get(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=request.candidate_id,
        )
        if CandidateState(latest.state) is not CandidateState.VERIFYING:
            # Never overwrite a concurrent lifecycle owner. The request/run remain
            # evidence, but no current-verdict attachment is made.
            await self._emit_after_verification(
                tenant_id=tenant_id,
                project_id=project_id,
                request=terminal_request,
                run=run,
                candidate=latest,
            )
            return CandidateVerificationExecution(terminal_request, run, latest)
        candidate = await self._candidates.transition(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=request.candidate_id,
            target=target,
            detail=terminal_request.reason,
            verification_run_id=run.verification_run_id,
        )
        await self._emit_after_verification(
            tenant_id=tenant_id,
            project_id=project_id,
            request=terminal_request,
            run=run,
            candidate=candidate,
        )
        return CandidateVerificationExecution(terminal_request, run, candidate)

    async def _emit_after_verification(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        request: FrontendVerificationRequest,
        run: VerificationRun,
        candidate: FrontendCandidate,
    ) -> None:
        await self._lifecycle.emit(
            tenant_id=tenant_id,
            project_id=project_id,
            event_kind="AFTER_VERIFICATION",
            context={
                "verification_request_id": str(request.verification_request_id),
                "verification_run_id": str(run.verification_run_id),
                "candidate_id": str(candidate.candidate_id),
                "request_state": request.state,
                "run_status": run.status,
                "candidate_state": candidate.state,
            },
        )

    async def _block_before_run(
        self, request: FrontendVerificationRequest, exc: DdeError
    ) -> CandidateVerificationExecution:
        blocked = await self._requests.mark_blocked(
            tenant_id=request.tenant_id,
            project_id=request.project_id,
            verification_request_id=request.verification_request_id,
            reason=f"verification precondition blocked: {exc}",
        )
        candidate = await self._candidates.get(
            tenant_id=request.tenant_id,
            project_id=request.project_id,
            candidate_id=request.candidate_id,
        )
        if CandidateState(candidate.state) is CandidateState.READY:
            candidate = await self._candidates.transition(
                tenant_id=request.tenant_id,
                project_id=request.project_id,
                candidate_id=request.candidate_id,
                target=CandidateState.BLOCKED,
                detail=blocked.reason,
            )
        return CandidateVerificationExecution(blocked, None, candidate)

    async def _resolve_context(
        self, *, tenant_id: UUID, project_id: UUID, request: FrontendVerificationRequest
    ) -> _ExecutionContext:
        if request.task_id is None or not request.acceptance_oracle_version:
            raise DdeError(
                "CONTEXT_INCOMPLETE",
                "verification request has no complete AcceptanceOracle binding",
                retryable=False,
            )
        if not request.content_hash:
            raise DdeError(
                "CONTEXT_INCOMPLETE",
                "verification request has no LIVE content hash",
                retryable=False,
            )
        preview = await self._previews.get(
            tenant_id=tenant_id,
            project_id=project_id,
            preview_session_id=request.preview_session_id,
        )
        if PreviewState(preview.state) is not PreviewState.LIVE:
            raise DdeError(
                "VERSION_CONFLICT",
                f"preview is {preview.state}, not LIVE",
                retryable=False,
            )
        latest_preview = await self._previews.latest_for_candidate(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=request.candidate_id,
        )
        if (
            latest_preview is None
            or latest_preview.preview_session_id != preview.preview_session_id
        ):
            raise DdeError(
                "VERSION_CONFLICT",
                "verification request does not target the candidate's latest preview",
                retryable=False,
            )
        if (
            preview.candidate_id != request.candidate_id
            or preview.screen_key != request.screen_key
            or preview.content_hash != request.content_hash
            or preview.candidate_pxg_revision != request.candidate_pxg_revision
        ):
            raise DdeError(
                "VERSION_CONFLICT",
                "verification request no longer matches the LIVE preview identity",
                retryable=False,
            )
        if preview.workspace_id is None or preview.document_path is None:
            raise DdeError(
                "CONTEXT_INCOMPLETE",
                "LIVE preview has no materialized candidate document",
                retryable=False,
            )
        candidate = await self._candidates.get(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=request.candidate_id,
        )
        if CandidateState(candidate.state) is not CandidateState.READY:
            raise DdeError(
                "VERSION_CONFLICT",
                f"candidate is {candidate.state}, not READY for verification",
                retryable=False,
            )
        if candidate.workspace_id != preview.workspace_id:
            raise DdeError(
                "VERSION_CONFLICT",
                "candidate workspace no longer matches its LIVE preview",
                retryable=False,
            )
        workspace = await self._workspaces.get_workspace(
            tenant_id=tenant_id,
            project_id=project_id,
            workspace_id=preview.workspace_id,
        )
        if not workspace.workspace_path:
            raise DdeError(
                "CONTEXT_INCOMPLETE",
                "candidate workspace has no filesystem path",
                retryable=False,
            )
        document = resolve_within_workspace(
            Path(workspace.workspace_path), preview.document_path
        )
        if not document.is_file():
            raise DdeError(
                "CONTEXT_INCOMPLETE",
                "candidate preview document is missing",
                retryable=False,
                details={"document_path": preview.document_path},
            )
        task = await self._missions.get_task(
            tenant_id=tenant_id, project_id=project_id, task_id=request.task_id
        )
        if task.mission_id != request.mission_id:
            raise DdeError(
                "POLICY_DENIED",
                "Acceptance task does not belong to the request mission",
                retryable=False,
            )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            oracle = await self._oracles.get_by_version(
                uow.connection, request.task_id, request.acceptance_oracle_version
            )
        if oracle is None:
            raise DdeError(
                "CONTEXT_INCOMPLETE",
                "bound AcceptanceOracle no longer resolves",
                retryable=False,
            )
        oracle_kinds = frozenset(
            outcome.evidence_binding.kind
            for outcome in [*oracle.observable_outcomes, *oracle.negative_cases]
        )
        missing = sorted(set(request.required_kinds) - oracle_kinds)
        if missing:
            raise DdeError(
                "VERSION_CONFLICT",
                "AcceptanceOracle no longer carries all requested verification kinds",
                retryable=False,
                details={"missing_kinds": missing},
            )
        unsupported = sorted(oracle_kinds & _UNSUPPORTED_DEFAULT_KINDS)
        if unsupported and (
            ("security_scan" in unsupported and self._security is None)
            or ("android_scan" in unsupported and self._android is None)
            or ("db_assertion" in unsupported and self._database is None)
        ):
            raise DdeError(
                "CONTEXT_INCOMPLETE",
                "candidate verification has no admitted runtime for all bound "
                "check kinds",
                retryable=False,
                details={"kinds": unsupported},
            )
        attempts = await self._attempts.list_for_task(
            tenant_id=tenant_id, project_id=project_id, task_id=task.task_id
        )
        if not attempts:
            raise DdeError(
                "CONTEXT_INCOMPLETE",
                "Acceptance task has no real TaskAttempt/ExecutionPlan identity "
                "for capability leasing",
                retryable=False,
            )
        attempt = max(attempts, key=lambda item: item.sequence)
        return _ExecutionContext(
            task=task,
            workspace=workspace,
            oracle=oracle,
            execution_plan_id=attempt.execution_plan_id,
            oracle_kinds=oracle_kinds,
            revision_fingerprint=request.content_hash,
            render_url=document.as_uri(),
        )

    async def _capabilities(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        request: FrontendVerificationRequest,
        task: Task,
        execution_plan_id: UUID,
        oracle_kinds: frozenset[str],
    ) -> tuple[BrowserCapability | None, VisualCriticCapability | None]:
        browser: BrowserCapability | None = None
        critic: VisualCriticCapability | None = None
        if oracle_kinds & _BROWSER_KINDS:
            lease = await self._request_capability(
                tenant_id=tenant_id,
                project_id=project_id,
                request=request,
                task=task,
                execution_plan_id=execution_plan_id,
                capability_id=CAPABILITY_BROWSER,
            )
            browser = LeaseBoundBrowserCapability(
                leases=self._leases,
                tenant_id=tenant_id,
                project_id=project_id,
                lease_id=lease,
                inner=self._browser_factory(),
            )
        if "visual_critique" in oracle_kinds:
            lease = await self._request_capability(
                tenant_id=tenant_id,
                project_id=project_id,
                request=request,
                task=task,
                execution_plan_id=execution_plan_id,
                capability_id=CAPABILITY_VISUAL_CRITIQUE,
            )
            critic = LeaseBoundVisualCriticCapability(
                leases=self._leases,
                tenant_id=tenant_id,
                project_id=project_id,
                lease_id=lease,
                inner=self._visual_critic_factory(),
            )
        return browser, critic

    async def _request_capability(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        request: FrontendVerificationRequest,
        task: Task,
        execution_plan_id: UUID,
        capability_id: str,
    ) -> UUID:
        lease = await self._leases.request(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=task.mission_id,
            task_id=task.task_id,
            execution_plan_id=execution_plan_id,
            capability_id=capability_id,
            capability_version="1",
            requested_by="engine.studio.candidate_verification",
            idempotency_key=f"frontend-verification:{request.verification_request_id}:lease:{capability_id}",
            worker_run_id=None,
            resource_scope={
                "candidate_id": str(request.candidate_id),
                "preview_session_id": str(request.preview_session_id),
                "screen_key": request.screen_key,
            },
            operation_scope="verify",
            constraints={"content_hash": request.content_hash or ""},
        )
        if lease.status not in {"GRANTED", "ACTIVE"}:
            raise DdeError(
                "POLICY_DENIED",
                f"{capability_id} lease was {lease.status}: "
                f"{lease.denied_reason or 'not granted'}",
                retryable=False,
                details={"lease_id": str(lease.lease_id)},
            )
        return lease.lease_id


@dataclass(frozen=True)
class _ExecutionContext:
    task: Task
    workspace: Workspace
    oracle: AcceptanceOracle
    execution_plan_id: UUID
    oracle_kinds: frozenset[str]
    revision_fingerprint: str
    render_url: str


def _default_browser() -> BrowserCapability:
    from adapters.playwright.probe import PlaywrightBrowserProbe

    return PlaywrightBrowserProbe()


def _default_visual_critic() -> VisualCriticCapability:
    from adapters.visual_critic.adapter import LocalMultimodalVisualCritic

    return LocalMultimodalVisualCritic()
