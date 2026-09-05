"""Conversation reasoning/permission/tool/fallback policy authority."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.ai_conversation_policy import AiConversationPolicy
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.fabric.repository import FabricRepository
from engine.fabric.tables import ai_conversation_policies

DEFAULT_CONTEXT_TOKENS = 24_000


def policy_hash(policy: AiConversationPolicy) -> str:
    payload = policy.model_dump(mode="json", exclude={"created_at", "updated_at"})
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class ConversationPolicyService:
    def __init__(self, engine: AsyncEngine) -> None:
        self.repo = FabricRepository(engine)

    async def create(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        name: str,
        reasoning_effort: str = "NORMAL",
        permission_profile: str = "APPROVAL_GATED",
        toolset_ids: list[str] | None = None,
        allowed_capability_ids: list[str] | None = None,
        denied_capability_ids: list[str] | None = None,
        fallback_chain: list[dict[str, object]] | None = None,
        max_turns: int | None = None,
        context_token_budget: int = DEFAULT_CONTEXT_TOKENS,
        cost_budget_usd: float | None = None,
        quality_priority: int = 90,
        latency_priority: int = 40,
        independent_review_required: bool = False,
        created_by: UUID | None = None,
    ) -> AiConversationPolicy:
        if not name.strip():
            raise DdeError("VALIDATION_FAILED", "policy name is required")
        allowed = set(allowed_capability_ids or [])
        denied = set(denied_capability_ids or [])
        overlap = sorted(allowed & denied)
        if overlap:
            raise DdeError(
                "VALIDATION_FAILED",
                "a capability cannot be both allowed and denied",
                details={"capability_ids": overlap},
            )
        if max_turns is not None and max_turns < 1:
            raise DdeError("VALIDATION_FAILED", "max_turns must be positive")
        if context_token_budget < 1:
            raise DdeError("VALIDATION_FAILED", "context token budget must be positive")
        if cost_budget_usd is not None and cost_budget_usd < 0:
            raise DdeError("VALIDATION_FAILED", "cost budget cannot be negative")
        now = datetime.now(UTC)
        values = dict(
            policy_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            name=name.strip(),
            reasoning_effort=reasoning_effort,
            permission_profile=permission_profile,
            toolset_ids=toolset_ids or [],
            allowed_capability_ids=sorted(allowed),
            denied_capability_ids=sorted(denied),
            fallback_chain=fallback_chain or [],
            max_turns=max_turns,
            context_token_budget=context_token_budget,
            cost_budget_usd=cost_budget_usd,
            quality_priority=quality_priority,
            latency_priority=latency_priority,
            independent_review_required=independent_review_required,
            created_by=created_by,
            lock_version=1,
            created_at=now,
            updated_at=now,
        )
        # Pydantic validates enum/range-shaped wire data before PostgreSQL sees it.
        AiConversationPolicy.model_validate(values)
        return await self.repo.insert_model(
            table=ai_conversation_policies,
            model=AiConversationPolicy,
            tenant_id=tenant_id,
            project_id=project_id,
            values=values,
        )

    async def get(
        self, *, tenant_id: UUID, project_id: UUID, policy_id: UUID
    ) -> AiConversationPolicy:
        return await self.repo.get_model(
            table=ai_conversation_policies,
            model=AiConversationPolicy,
            id_column="policy_id",
            object_id=policy_id,
            tenant_id=tenant_id,
            project_id=project_id,
        )

    async def list(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> tuple[AiConversationPolicy, ...]:
        return await self.repo.list_models(
            table=ai_conversation_policies,
            model=AiConversationPolicy,
            tenant_id=tenant_id,
            project_id=project_id,
            order_by=(ai_conversation_policies.c.name.asc(),),
        )
