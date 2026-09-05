"""Cross-surface mutation coordinator for DDE-069 Frontend Studio.

`MutationExecutor` remains the sole mutation-log writer. This coordinator owns
what every *successful* candidate mutation means to the rest of Frontend
Studio: any code-backed preview describing the old candidate becomes STALE and
any outstanding DDE-068 verification request becomes SUPERSEDED. Inspector,
Chat and explicit revert all use this service so no surface can leave stale
LIVE/VERIFIED evidence behind.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.frontend_mutation import FrontendMutation
from engine.fabric.lifecycle import FabricLifecycleService
from engine.studio.mutations.executor import MutationExecutor, MutationOutcome
from engine.studio.mutations.planner import MutationRequest
from engine.studio.preview_runtime.service import PreviewService
from engine.studio.verification_requests import CandidateVerificationRequestService

_INVALIDATION_DETAIL = "governed mutation changed the candidate; rerender required"
_VERIFICATION_DETAIL = (
    "governed mutation changed the candidate; DDE-068 verification must run "
    "against the new preview"
)


@dataclass(frozen=True)
class GovernedMutationOutcome:
    mutation: MutationOutcome
    invalidated_preview_session_ids: tuple[UUID, ...]
    superseded_verification_request_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class GovernedRevertOutcome:
    compensating_mutation: FrontendMutation
    invalidated_preview_session_ids: tuple[UUID, ...]
    superseded_verification_request_ids: tuple[UUID, ...]


class GovernedMutationService:
    """Apply/revert candidate mutations and invalidate every stale derivative."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        executor: MutationExecutor | None = None,
        previews: PreviewService | None = None,
        verification_requests: CandidateVerificationRequestService | None = None,
        lifecycle: FabricLifecycleService | None = None,
    ) -> None:
        self._engine = engine
        self._executor = executor or MutationExecutor(engine)
        self._previews = previews or PreviewService(engine, mutations=self._executor)
        self._verification_requests = (
            verification_requests
            or CandidateVerificationRequestService(engine, mutations=self._executor)
        )
        self._lifecycle = lifecycle or FabricLifecycleService(engine)

    async def apply(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
        requests: list[MutationRequest],
        contract_version: int | None = None,
        design_system_hash: str | None = None,
        conversation_id: UUID | None = None,
        principal_id: UUID | None = None,
    ) -> GovernedMutationOutcome:
        context = {
            "candidate_id": str(candidate_id),
            "request_count": len(requests),
            "operations": [request.operation for request in requests],
        }
        await self._lifecycle.emit(
            tenant_id=tenant_id,
            project_id=project_id,
            event_kind="BEFORE_MUTATION",
            context=context,
            conversation_id=conversation_id,
            principal_id=principal_id,
        )
        mutation = await self._executor.apply(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
            requests=requests,
            contract_version=contract_version,
            design_system_hash=design_system_hash,
        )
        invalidated: tuple[UUID, ...] = ()
        superseded: tuple[UUID, ...] = ()
        if mutation.applied:
            invalidated, superseded = await self._invalidate(
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=candidate_id,
            )
        await self._lifecycle.emit(
            tenant_id=tenant_id,
            project_id=project_id,
            event_kind="AFTER_MUTATION",
            context={
                **context,
                "applied_count": len(mutation.applied),
                "refused_count": len(mutation.refused),
                "mutation_ids": [str(item.mutation_id) for item in mutation.applied],
            },
            conversation_id=conversation_id,
            principal_id=principal_id,
        )
        return GovernedMutationOutcome(mutation, invalidated, superseded)

    async def revert(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
        mutation_id: UUID,
        conversation_id: UUID | None = None,
        principal_id: UUID | None = None,
    ) -> GovernedRevertOutcome:
        context: dict[str, object] = {
            "candidate_id": str(candidate_id),
            "revert_mutation_id": str(mutation_id),
        }
        await self._lifecycle.emit(
            tenant_id=tenant_id,
            project_id=project_id,
            event_kind="BEFORE_MUTATION",
            context=context,
            conversation_id=conversation_id,
            principal_id=principal_id,
        )
        compensating = await self._executor.revert(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
            mutation_id=mutation_id,
        )
        invalidated, superseded = await self._invalidate(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
        )
        await self._lifecycle.emit(
            tenant_id=tenant_id,
            project_id=project_id,
            event_kind="AFTER_MUTATION",
            context={
                **context,
                "compensating_mutation_id": str(compensating.mutation_id),
            },
            conversation_id=conversation_id,
            principal_id=principal_id,
        )
        return GovernedRevertOutcome(compensating, invalidated, superseded)

    async def history(
        self, *, tenant_id: UUID, project_id: UUID, candidate_id: UUID
    ) -> tuple[FrontendMutation, ...]:
        return await self._executor.history(
            tenant_id=tenant_id, project_id=project_id, candidate_id=candidate_id
        )

    async def _invalidate(
        self, *, tenant_id: UUID, project_id: UUID, candidate_id: UUID
    ) -> tuple[tuple[UUID, ...], tuple[UUID, ...]]:
        previews = await self._previews.invalidate_candidate(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
            detail=_INVALIDATION_DETAIL,
        )
        requests = await self._verification_requests.supersede_for_candidate(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
            reason=_VERIFICATION_DETAIL,
        )
        return (
            tuple(item.preview_session_id for item in previews),
            tuple(requests),
        )
