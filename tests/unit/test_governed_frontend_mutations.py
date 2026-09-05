"""Pure authority tests for the cross-surface Frontend mutation coordinator."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.frontend_mutation import FrontendMutation, Preconditions
from engine.studio.candidates.lifecycle import CandidateState
from engine.studio.mutations.executor import MutationExecutor, MutationOutcome
from engine.studio.mutations.governed import GovernedMutationService
from engine.studio.mutations.planner import MutationRequest
from engine.studio.preview_runtime.service import PreviewService
from engine.studio.verification_requests import CandidateVerificationRequestService


def _mutation(*, sequence: int = 1) -> FrontendMutation:
    now = datetime.now(UTC)
    return FrontendMutation(
        mutation_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        candidate_id=uuid4(),
        sequence=sequence,
        operation="SET_PROPERTY",
        target_key="screens/checkout#hero",
        origin="CHAT",
        status="APPLIED",
        payload={"property": "spacing", "value": "space4"},
        inverse={"operation": "SET_PROPERTY", "property": "spacing", "value": "space2"},
        preconditions=Preconditions(
            pxg_revision=4,
            candidate_base_revision=4,
            frontend_contract_version=None,
            design_system_hash=None,
            effective_lock_hash="locks-v1",
        ),
        created_at=now,
        updated_at=now,
    )


class _Executor:
    def __init__(self, outcome: MutationOutcome, reverted: FrontendMutation) -> None:
        self.outcome = outcome
        self.reverted = reverted
        self.history_rows: tuple[FrontendMutation, ...] = (reverted,)
        self.apply_calls = 0
        self.revert_calls = 0

    async def apply(self, **_: object) -> MutationOutcome:
        self.apply_calls += 1
        return self.outcome

    async def revert(self, **_: object) -> FrontendMutation:
        self.revert_calls += 1
        return self.reverted

    async def history(self, **_: object) -> tuple[FrontendMutation, ...]:
        return self.history_rows


class _Previews:
    def __init__(self, preview_id: UUID) -> None:
        self.preview_id = preview_id
        self.calls = 0

    async def invalidate_candidate(self, **_: object) -> tuple[SimpleNamespace, ...]:
        self.calls += 1
        return (SimpleNamespace(preview_session_id=self.preview_id),)


class _Requests:
    def __init__(self, request_id: UUID) -> None:
        self.request_id = request_id
        self.calls = 0

    async def supersede_for_candidate(self, **_: object) -> tuple[UUID, ...]:
        self.calls += 1
        return (self.request_id,)


def _service(
    executor: _Executor, previews: _Previews, requests: _Requests
) -> GovernedMutationService:
    return GovernedMutationService(
        cast(AsyncEngine, object()),
        executor=cast(MutationExecutor, executor),
        previews=cast(PreviewService, previews),
        verification_requests=cast(CandidateVerificationRequestService, requests),
    )


@pytest.mark.asyncio
async def test_successful_mutation_invalidates_preview_and_verification() -> None:
    applied = _mutation()
    executor = _Executor(
        MutationOutcome((applied,), (), CandidateState.DIRTY, 5), applied
    )
    preview_id = uuid4()
    request_id = uuid4()
    previews = _Previews(preview_id)
    requests = _Requests(request_id)
    service = _service(executor, previews, requests)

    result = await service.apply(
        tenant_id=uuid4(),
        project_id=uuid4(),
        candidate_id=uuid4(),
        requests=[
            MutationRequest(
                operation="SET_PROPERTY",
                target_key="screens/checkout#hero",
                origin="CHAT",
                payload={"property": "spacing", "value": "space4"},
            )
        ],
    )

    assert result.mutation.applied == (applied,)
    assert result.invalidated_preview_session_ids == (preview_id,)
    assert result.superseded_verification_request_ids == (request_id,)
    assert previews.calls == 1
    assert requests.calls == 1


@pytest.mark.asyncio
async def test_refused_only_mutation_does_not_invalidate_current_evidence() -> None:
    executor = _Executor(MutationOutcome((), (), CandidateState.READY, 4), _mutation())
    previews = _Previews(uuid4())
    requests = _Requests(uuid4())
    service = _service(executor, previews, requests)

    result = await service.apply(
        tenant_id=uuid4(), project_id=uuid4(), candidate_id=uuid4(), requests=[]
    )

    assert result.invalidated_preview_session_ids == ()
    assert result.superseded_verification_request_ids == ()
    assert previews.calls == 0
    assert requests.calls == 0


@pytest.mark.asyncio
async def test_revert_invalidates_every_derivative_of_the_old_candidate() -> None:
    compensating = _mutation(sequence=2)
    executor = _Executor(
        MutationOutcome((compensating,), (), CandidateState.DIRTY, 6), compensating
    )
    preview_id = uuid4()
    request_id = uuid4()
    previews = _Previews(preview_id)
    requests = _Requests(request_id)
    service = _service(executor, previews, requests)

    result = await service.revert(
        tenant_id=uuid4(),
        project_id=uuid4(),
        candidate_id=uuid4(),
        mutation_id=uuid4(),
    )

    assert result.compensating_mutation is compensating
    assert result.invalidated_preview_session_ids == (preview_id,)
    assert result.superseded_verification_request_ids == (request_id,)
    assert executor.revert_calls == 1


@pytest.mark.asyncio
async def test_history_is_the_executor_history_not_a_second_chat_log() -> None:
    row = _mutation()
    executor = _Executor(MutationOutcome((), (), CandidateState.READY, 4), row)
    service = _service(executor, _Previews(uuid4()), _Requests(uuid4()))

    history = await service.history(
        tenant_id=uuid4(), project_id=uuid4(), candidate_id=row.candidate_id
    )

    assert history == (row,)
