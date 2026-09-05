from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from engine.contracts.acceptance_oracle import AcceptanceOracle
from engine.contracts.frontend_candidate import FrontendCandidate
from engine.contracts.frontend_verification_request import FrontendVerificationRequest
from engine.contracts.task import Task
from engine.contracts.verification_run import VerificationRun
from engine.contracts.workspace import Workspace
from engine.studio.candidates.lifecycle import CandidateState
from engine.studio.verification_execution import (
    CandidateVerificationExecutionService,
    _ExecutionContext,
)


class _Requests:
    def __init__(
        self, request: FrontendVerificationRequest, *, supersede: bool = False
    ):
        self.request = request
        self.supersede = supersede

    async def get(self, **_: object) -> FrontendVerificationRequest:
        return self.request

    async def mark_running(self, **_: object) -> FrontendVerificationRequest:
        self.request = self.request.model_copy(
            update={"state": "RUNNING", "lock_version": self.request.lock_version + 1}
        )
        return self.request

    async def mark_blocked(
        self, *, reason: str, **_: object
    ) -> FrontendVerificationRequest:
        self.request = self.request.model_copy(
            update={
                "state": "BLOCKED",
                "reason": reason,
                "lock_version": self.request.lock_version + 1,
            }
        )
        return self.request

    async def record_run(
        self,
        *,
        verification_run_id: UUID,
        terminal_state: str,
        reason: str,
        **_: object,
    ) -> FrontendVerificationRequest:
        self.request = self.request.model_copy(
            update={
                "state": "SUPERSEDED" if self.supersede else terminal_state,
                "reason": "candidate changed" if self.supersede else reason,
                "verification_run_ids": [verification_run_id],
                "lock_version": self.request.lock_version + 1,
            }
        )
        return self.request


class _Candidates:
    def __init__(self, candidate: FrontendCandidate):
        self.candidate = candidate
        self.transitions: list[CandidateState] = []

    async def get(self, **_: object) -> FrontendCandidate:
        return self.candidate

    async def transition(
        self,
        *,
        target: CandidateState,
        detail: str | None = None,
        verification_run_id: UUID | None = None,
        **_: object,
    ) -> FrontendCandidate:
        self.transitions.append(target)
        update: dict[str, object] = {"state": target.value, "state_detail": detail}
        if verification_run_id is not None:
            update["verification_run_id"] = verification_run_id
        self.candidate = self.candidate.model_copy(update=update)
        return self.candidate


class _Runner:
    def __init__(self, run: VerificationRun):
        self.run = run
        self.calls: list[dict[str, object]] = []

    async def run_workspace_revision(self, **kwargs: object) -> VerificationRun:
        self.calls.append(dict(kwargs))
        return self.run


def _request(
    *, tenant: UUID, project: UUID, mission: UUID, candidate: UUID
) -> FrontendVerificationRequest:
    now = datetime.now(UTC)
    return FrontendVerificationRequest(
        verification_request_id=uuid4(),
        tenant_id=tenant,
        project_id=project,
        mission_id=mission,
        candidate_id=candidate,
        preview_session_id=uuid4(),
        screen_key="screens/checkout",
        viewport="1440",
        candidate_pxg_revision=4,
        source_revision="source",
        content_hash="candidate-hash",
        task_id=uuid4(),
        acceptance_oracle_version="oracle-v1",
        required_kinds=["silhouette", "visual_critique"],
        state="PENDING",
        verification_run_ids=[],
        lock_version=1,
        created_at=now,
        updated_at=now,
    )


def _candidate(
    *, tenant: UUID, project: UUID, mission: UUID, candidate_id: UUID
) -> FrontendCandidate:
    now = datetime.now(UTC)
    return FrontendCandidate(
        candidate_id=candidate_id,
        tenant_id=tenant,
        project_id=project,
        mission_id=mission,
        workspace_id=uuid4(),
        title="Candidate",
        state="READY",
        origin="DIRECT_EDIT",
        base_pxg_revision=4,
        base_contract_version=None,
        scope_keys=["screens/checkout"],
        verification_run_id=None,
        provenance={},
        state_detail=None,
        superseded_by=None,
        promoted_at=None,
        lock_version=1,
        created_at=now,
        updated_at=now,
    )


def _task(*, tenant: UUID, project: UUID, mission: UUID, task_id: UUID) -> Task:
    now = datetime.now(UTC)
    return Task(
        task_id=task_id,
        tenant_id=tenant,
        project_id=project,
        mission_id=mission,
        graph_id=uuid4(),
        title="Frontend",
        intent="verify candidate",
        task_class="implementation",
        requirement_refs=[],
        feature_refs=[],
        success_criteria=[],
        expected_write_scope=["prototypes/screens/**"],
        expected_read_scope=[],
        blast_radius="local",
        risk_class="medium",
        estimated_effort="s",
        autonomy_ceiling=2,
        requires_approval=False,
        status="EXECUTING",
        lock_version=1,
        created_at=now,
        updated_at=now,
    )


def _workspace(
    *, tenant: UUID, project: UUID, mission: UUID, task_id: UUID
) -> Workspace:
    now = datetime.now(UTC)
    return Workspace(
        workspace_id=uuid4(),
        tenant_id=tenant,
        project_id=project,
        mission_id=mission,
        task_id=task_id,
        execution_environment_id=uuid4(),
        base_revision="base",
        current_revision="current",
        workspace_path="/tmp/candidate",
        policy={},
        status="READY",
        lock_version=1,
        created_at=now,
        updated_at=now,
    )


def _oracle(
    *, tenant: UUID, project: UUID, mission: UUID, task_id: UUID
) -> AcceptanceOracle:
    now = datetime.now(UTC)
    return AcceptanceOracle(
        oracle_id=uuid4(),
        tenant_id=tenant,
        project_id=project,
        mission_id=mission,
        task_id=task_id,
        oracle_version="oracle-v1",
        scope="task",
        requirement_refs=[],
        feature_refs=[],
        observable_outcomes=[],
        domain_invariants=[],
        negative_cases=[],
        minimum_confidence=1.0,
        human_assertions=[],
        created_at=now,
        updated_at=now,
    )


def _run(
    *,
    tenant: UUID,
    project: UUID,
    mission: UUID,
    task_id: UUID,
    candidate_id: UUID,
    workspace_id: UUID,
) -> VerificationRun:
    now = datetime.now(UTC)
    return VerificationRun(
        verification_run_id=uuid4(),
        tenant_id=tenant,
        project_id=project,
        mission_id=mission,
        task_id=task_id,
        task_attempt_id=None,
        worker_run_id=None,
        subject_kind="FRONTEND_CANDIDATE",
        subject_id=candidate_id,
        workspace_id=workspace_id,
        oracle_id=uuid4(),
        sequence=1,
        status="PASSED",
        confidence=1.0,
        check_results=[],
        outcome_results=[],
        negative_case_results=[],
        evidence_refs=[],
        started_at=now,
        ended_at=now,
        created_at=now,
        updated_at=now,
    )


class _Service(CandidateVerificationExecutionService):
    def __init__(
        self,
        *,
        requests: _Requests,
        candidates: _Candidates,
        context: _ExecutionContext,
        runner: _Runner,
    ):
        super().__init__(
            None,  # type: ignore[arg-type]
            requests=requests,  # type: ignore[arg-type]
            previews=object(),  # type: ignore[arg-type]
            candidates=candidates,  # type: ignore[arg-type]
            workspaces=object(),  # type: ignore[arg-type]
            missions=object(),  # type: ignore[arg-type]
            attempts=object(),  # type: ignore[arg-type]
            leases=object(),  # type: ignore[arg-type]
            runner_factory=lambda *args, **kwargs: runner,  # type: ignore[arg-type]
        )
        self.context = context

    async def _resolve_context(self, **_: object) -> _ExecutionContext:
        return self.context

    async def _capabilities(self, **_: object) -> tuple[None, None]:
        return None, None


@pytest.mark.asyncio
async def test_passed_candidate_run_attaches_only_after_real_run_completes() -> None:
    tenant, project, mission, candidate_id = uuid4(), uuid4(), uuid4(), uuid4()
    request = _request(
        tenant=tenant, project=project, mission=mission, candidate=candidate_id
    )
    candidate = _candidate(
        tenant=tenant, project=project, mission=mission, candidate_id=candidate_id
    )
    task = _task(
        tenant=tenant, project=project, mission=mission, task_id=request.task_id
    )  # type: ignore[arg-type]
    workspace = _workspace(
        tenant=tenant, project=project, mission=mission, task_id=task.task_id
    )
    oracle = _oracle(
        tenant=tenant, project=project, mission=mission, task_id=task.task_id
    )
    run = _run(
        tenant=tenant,
        project=project,
        mission=mission,
        task_id=task.task_id,
        candidate_id=candidate_id,
        workspace_id=workspace.workspace_id,
    )
    requests = _Requests(request)
    candidates = _Candidates(candidate)
    runner = _Runner(run)
    service = _Service(
        requests=requests,
        candidates=candidates,
        context=_ExecutionContext(
            task,
            workspace,
            oracle,
            uuid4(),
            frozenset(),
            "candidate-hash",
            "file:///candidate.html",
        ),
        runner=runner,
    )

    result = await service.execute(
        tenant_id=tenant,
        project_id=project,
        mission_id=mission,
        verification_request_id=request.verification_request_id,
    )

    assert result.request.state == "PASSED"
    assert result.candidate.state == "VERIFIED"
    assert result.candidate.verification_run_id == run.verification_run_id
    assert candidates.transitions == [CandidateState.VERIFYING, CandidateState.VERIFIED]
    assert runner.calls[0]["subject_id"] == candidate_id
    assert runner.calls[0]["render_url_override"] == "file:///candidate.html"


@pytest.mark.asyncio
async def test_superseded_in_flight_run_never_restores_verified_candidate() -> None:
    tenant, project, mission, candidate_id = uuid4(), uuid4(), uuid4(), uuid4()
    request = _request(
        tenant=tenant, project=project, mission=mission, candidate=candidate_id
    )
    candidate = _candidate(
        tenant=tenant, project=project, mission=mission, candidate_id=candidate_id
    )
    task = _task(
        tenant=tenant, project=project, mission=mission, task_id=request.task_id
    )  # type: ignore[arg-type]
    workspace = _workspace(
        tenant=tenant, project=project, mission=mission, task_id=task.task_id
    )
    oracle = _oracle(
        tenant=tenant, project=project, mission=mission, task_id=task.task_id
    )
    run = _run(
        tenant=tenant,
        project=project,
        mission=mission,
        task_id=task.task_id,
        candidate_id=candidate_id,
        workspace_id=workspace.workspace_id,
    )
    requests = _Requests(request, supersede=True)
    candidates = _Candidates(candidate)
    runner = _Runner(run)
    service = _Service(
        requests=requests,
        candidates=candidates,
        context=_ExecutionContext(
            task,
            workspace,
            oracle,
            uuid4(),
            frozenset(),
            "candidate-hash",
            "file:///candidate.html",
        ),
        runner=runner,
    )

    result = await service.execute(
        tenant_id=tenant,
        project_id=project,
        mission_id=mission,
        verification_request_id=request.verification_request_id,
    )

    assert result.request.state == "SUPERSEDED"
    assert result.request.verification_run_ids == [run.verification_run_id]
    assert result.candidate.state == "VERIFYING"
    assert result.candidate.verification_run_id is None
    assert candidates.transitions == [CandidateState.VERIFYING]
