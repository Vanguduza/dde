"""Provider invocation lineage, budget gates and visible fallback accounting."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.agent_interop_endpoint import AgentInteropEndpoint
from engine.contracts.ai_conversation_policy import AiConversationPolicy
from engine.contracts.ai_provider_invocation import AiProviderInvocation
from engine.contracts.worker_session import WorkerSession
from engine.core.errors import BudgetExhaustedError, DdeError
from engine.core.ids import uuid7
from engine.fabric.repository import FabricRepository
from engine.fabric.tables import (
    agent_interop_endpoints,
    ai_conversation_policies,
    ai_provider_invocations,
    worker_sessions,
)
from engine.truth.db import open_unit_of_work


class ProviderInvocationService:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self.repo = FabricRepository(engine)

    async def prepare(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        endpoint_id: UUID,
        reasoning_effort: str,
        prompt_hash: str,
        context_hash: str,
        policy_id: UUID | None = None,
        worker_session_id: UUID | None = None,
        turn_id: UUID | None = None,
        fallback_parent_id: UUID | None = None,
        requested_profile_id: str | None = None,
        requested_model_id: str | None = None,
    ) -> AiProviderInvocation:
        endpoint = await self.repo.get_model(
            table=agent_interop_endpoints,
            model=AgentInteropEndpoint,
            id_column="endpoint_id",
            object_id=endpoint_id,
            tenant_id=tenant_id,
            project_id=project_id,
        )
        if endpoint.certification_state != "CERTIFIED":
            raise DdeError(
                "CAPABILITY_UNAVAILABLE",
                "generative invocation requires a certified interop endpoint",
                details={"endpoint_id": str(endpoint_id)},
            )
        policy: AiConversationPolicy | None = None
        if policy_id:
            policy = await self.repo.get_model(
                table=ai_conversation_policies,
                model=AiConversationPolicy,
                id_column="policy_id",
                object_id=policy_id,
                tenant_id=tenant_id,
                project_id=project_id,
            )
            await self._enforce_budget(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=conversation_id,
                policy=policy,
            )
        if worker_session_id:
            session = await self.repo.get_model(
                table=worker_sessions,
                model=WorkerSession,
                id_column="worker_session_id",
                object_id=worker_session_id,
                tenant_id=tenant_id,
                project_id=project_id,
            )
            if session.endpoint_id != endpoint_id or session.state not in {
                "OPENING",
                "ACTIVE",
                "RESUMING",
            }:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "provider invocation/session endpoint or state mismatch",
                )
        requires_approval = bool(
            endpoint.certified_capabilities.get("requires_per_invocation_approval")
        )
        state = "APPROVAL_REQUIRED" if requires_approval else "PENDING"
        now = datetime.now(UTC)
        values: dict[str, object] = {
            "invocation_id": uuid7(),
            "tenant_id": tenant_id,
            "project_id": project_id,
            "conversation_id": conversation_id,
            "turn_id": turn_id,
            "worker_session_id": worker_session_id,
            "endpoint_id": endpoint_id,
            "fallback_parent_id": fallback_parent_id,
            "requested_profile_id": requested_profile_id,
            "requested_model_id": requested_model_id,
            "serving_model_id": None,
            "reasoning_effort": reasoning_effort,
            "state": state,
            "prompt_hash": prompt_hash,
            "context_hash": context_hash,
            "policy_hash": self._policy_hash(policy),
            "approval_id": None,
            "worker_run_id": None,
            "input_tokens": None,
            "output_tokens": None,
            "cache_tokens": None,
            "reasoning_tokens": None,
            "cost_usd": None,
            "latency_ms": None,
            "result_refs": [],
            "error_code": None,
            "error_detail": None,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "updated_at": now,
        }
        AiProviderInvocation.model_validate(values)
        return await self.repo.insert_model(
            table=ai_provider_invocations,
            model=AiProviderInvocation,
            tenant_id=tenant_id,
            project_id=project_id,
            values=values,
        )

    async def begin(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        invocation_id: UUID,
        approval_id: UUID | None = None,
        worker_run_id: UUID | None = None,
    ) -> AiProviderInvocation:
        current = await self.get(
            tenant_id=tenant_id, project_id=project_id, invocation_id=invocation_id
        )
        if current.state == "APPROVAL_REQUIRED" and approval_id is None:
            raise DdeError(
                "APPROVAL_REQUIRED",
                "provider invocation requires an explicit approval reference",
            )
        if current.state not in {"PENDING", "APPROVAL_REQUIRED"}:
            raise DdeError("VERSION_CONFLICT", "provider invocation cannot start")
        return await self._update_state(
            current,
            tenant_id=tenant_id,
            project_id=project_id,
            state="RUNNING",
            approval_id=approval_id,
            worker_run_id=worker_run_id,
            started_at=datetime.now(UTC),
        )

    async def complete(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        invocation_id: UUID,
        serving_model_id: str | None,
        input_tokens: int | None,
        output_tokens: int | None,
        cache_tokens: int | None,
        reasoning_tokens: int | None,
        cost_usd: float | None,
        latency_ms: int | None,
        result_refs: list[str],
    ) -> AiProviderInvocation:
        current = await self.get(
            tenant_id=tenant_id, project_id=project_id, invocation_id=invocation_id
        )
        if current.state != "RUNNING":
            raise DdeError("VERSION_CONFLICT", "only a running invocation may complete")
        return await self._update_state(
            current,
            tenant_id=tenant_id,
            project_id=project_id,
            state="COMPLETED",
            serving_model_id=serving_model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_tokens=cache_tokens,
            reasoning_tokens=reasoning_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            result_refs=result_refs,
            completed_at=datetime.now(UTC),
        )

    async def fail(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        invocation_id: UUID,
        error_code: str,
        error_detail: str,
    ) -> AiProviderInvocation:
        current = await self.get(
            tenant_id=tenant_id, project_id=project_id, invocation_id=invocation_id
        )
        if current.state in {"COMPLETED", "CANCELLED", "FAILED"}:
            raise DdeError(
                "VERSION_CONFLICT", "provider invocation is already terminal"
            )
        return await self._update_state(
            current,
            tenant_id=tenant_id,
            project_id=project_id,
            state="FAILED",
            error_code=error_code,
            error_detail=error_detail,
            completed_at=datetime.now(UTC),
        )

    async def get(
        self, *, tenant_id: UUID, project_id: UUID, invocation_id: UUID
    ) -> AiProviderInvocation:
        return await self.repo.get_model(
            table=ai_provider_invocations,
            model=AiProviderInvocation,
            id_column="invocation_id",
            object_id=invocation_id,
            tenant_id=tenant_id,
            project_id=project_id,
        )

    async def list_for_conversation(
        self, *, tenant_id: UUID, project_id: UUID, conversation_id: UUID
    ) -> tuple[AiProviderInvocation, ...]:
        return await self.repo.list_models(
            table=ai_provider_invocations,
            model=AiProviderInvocation,
            tenant_id=tenant_id,
            project_id=project_id,
            filters={"conversation_id": conversation_id},
            order_by=(ai_provider_invocations.c.created_at.desc(),),
        )

    async def _enforce_budget(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        policy: AiConversationPolicy,
    ) -> None:
        async with open_unit_of_work(
            self.engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                select(
                    func.count(ai_provider_invocations.c.invocation_id),
                    func.coalesce(func.sum(ai_provider_invocations.c.cost_usd), 0),
                ).where(ai_provider_invocations.c.conversation_id == conversation_id)
            )
            turns, cost = result.one()
        if policy.max_turns is not None and int(turns) >= policy.max_turns:
            raise BudgetExhaustedError(
                "conversation provider-turn budget exhausted",
                details={"max_turns": policy.max_turns, "observed": int(turns)},
            )
        if policy.cost_budget_usd is not None and float(cost) >= policy.cost_budget_usd:
            raise BudgetExhaustedError(
                "conversation provider-cost budget exhausted",
                details={
                    "cost_budget_usd": policy.cost_budget_usd,
                    "observed": float(cost),
                },
            )

    @staticmethod
    def _policy_hash(policy: AiConversationPolicy | None) -> str:
        if policy is None:
            return "UNBOUND"
        from engine.fabric.policies import policy_hash

        return policy_hash(policy)

    async def _update_state(
        self,
        current: AiProviderInvocation,
        *,
        tenant_id: UUID,
        project_id: UUID,
        state: str,
        **values: object,
    ) -> AiProviderInvocation:
        # Invocation rows intentionally have no optimistic lock column. They are
        # append/terminal lineage, so update by current state as a CAS instead.
        async with open_unit_of_work(
            self.engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            from sqlalchemy import update

            result = await uow.connection.execute(
                update(ai_provider_invocations)
                .where(
                    ai_provider_invocations.c.invocation_id == current.invocation_id,
                    ai_provider_invocations.c.state == current.state,
                )
                .values(state=state, updated_at=datetime.now(UTC), **values)
                .returning(ai_provider_invocations)
            )
            row = result.mappings().one_or_none()
            if row is None:
                raise DdeError(
                    "VERSION_CONFLICT", "provider invocation changed concurrently"
                )
            await uow.commit()
        return AiProviderInvocation.model_validate(dict(row))
