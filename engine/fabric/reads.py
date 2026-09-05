"""Read projections for AI Conversation Fabric controls."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.provider_capacity_snapshot import ProviderCapacitySnapshot
from engine.fabric.automations import AutomationService
from engine.fabric.claims import ClaimService
from engine.fabric.context import ContextSnapshotService
from engine.fabric.experience import ExperienceService
from engine.fabric.hooks import HookService
from engine.fabric.interop import AgentInteropService
from engine.fabric.invocations import ProviderInvocationService
from engine.fabric.memory import MemoryService
from engine.fabric.policies import ConversationPolicyService
from engine.fabric.repository import FabricRepository
from engine.fabric.research import ResearchService
from engine.fabric.sessions import WorkerSessionService
from engine.fabric.skills import SkillService
from engine.fabric.tables import provider_capacity_snapshots
from engine.fabric.teams import AgentTeamService


def _dump(rows: object) -> object:
    if hasattr(rows, "model_dump"):
        return rows.model_dump(mode="json")
    if isinstance(rows, tuple):
        return [_dump(row) for row in rows]
    return rows


class FabricReadService:
    def __init__(self, engine: AsyncEngine) -> None:
        self.repo = FabricRepository(engine)
        self.policies = ConversationPolicyService(engine)
        self.interop = AgentInteropService(engine)
        self.sessions = WorkerSessionService(engine)
        self.invocations = ProviderInvocationService(engine)
        self.memory = MemoryService(engine)
        self.context = ContextSnapshotService(engine)
        self.skills = SkillService(engine)
        self.teams = AgentTeamService(engine)
        self.research = ResearchService(engine)
        self.automations = AutomationService(engine)
        self.hooks = HookService(engine)
        self.claims = ClaimService(engine)
        self.experience = ExperienceService(engine)

    async def project_snapshot(
        self, *, tenant_id: UUID, project_id: UUID, conversation_id: UUID | None = None
    ) -> dict[str, object]:
        endpoints = await self.interop.list_endpoints(
            tenant_id=tenant_id, project_id=project_id
        )
        sessions = await self.sessions.list_sessions(
            tenant_id=tenant_id, project_id=project_id
        )
        policies = await self.policies.list(tenant_id=tenant_id, project_id=project_id)
        skills = await self.skills.list_skills(
            tenant_id=tenant_id, project_id=project_id
        )
        capacities = await self.repo.list_models(
            table=provider_capacity_snapshots,
            model=ProviderCapacitySnapshot,
            tenant_id=tenant_id,
            project_id=project_id,
            order_by=(provider_capacity_snapshots.c.observed_at.desc(),),
            limit=100,
        )
        result: dict[str, object] = {
            "policies": _dump(policies),
            "endpoints": _dump(endpoints),
            "sessions": _dump(sessions),
            "skills": _dump(skills),
            "provider_capacity": _dump(capacities),
        }
        if conversation_id is not None:
            result["conversation"] = await self.conversation_snapshot(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=conversation_id,
            )
        return result

    async def conversation_snapshot(
        self, *, tenant_id: UUID, project_id: UUID, conversation_id: UUID
    ) -> dict[str, object]:
        invocations = await self.invocations.list_for_conversation(
            tenant_id=tenant_id, project_id=project_id, conversation_id=conversation_id
        )
        contexts = await self.context.list_for_conversation(
            tenant_id=tenant_id, project_id=project_id, conversation_id=conversation_id
        )
        teams = await self.teams.list_for_conversation(
            tenant_id=tenant_id, project_id=project_id, conversation_id=conversation_id
        )
        research = await self.research.list_for_conversation(
            tenant_id=tenant_id, project_id=project_id, conversation_id=conversation_id
        )
        automations = await self.automations.list_for_conversation(
            tenant_id=tenant_id, project_id=project_id, conversation_id=conversation_id
        )
        hooks = await self.hooks.list_hooks(
            tenant_id=tenant_id, project_id=project_id, conversation_id=conversation_id
        )
        return {
            "invocations": _dump(invocations),
            "context_snapshots": _dump(contexts),
            "teams": _dump(teams),
            "research": _dump(research),
            "automations": _dump(automations),
            "hooks": _dump(hooks),
        }

    async def memory_scope(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        scope_kind: str,
        scope_ref: str,
        status: str | None = None,
    ) -> list[object]:
        return _dump(
            await self.memory.list_scope(
                tenant_id=tenant_id,
                project_id=project_id,
                scope_kind=scope_kind,
                scope_ref=scope_ref,
                status=status,
            )
        )  # type: ignore[return-value]

    async def claims_for_turn(
        self, *, tenant_id: UUID, project_id: UUID, turn_id: UUID
    ) -> list[object]:
        return _dump(
            await self.claims.list_for_turn(
                tenant_id=tenant_id, project_id=project_id, turn_id=turn_id
            )
        )  # type: ignore[return-value]

    async def experience_records(
        self, *, tenant_id: UUID, project_id: UUID, task_id: UUID | None = None
    ) -> list[object]:
        return _dump(
            await self.experience.list_records(
                tenant_id=tenant_id, project_id=project_id, task_id=task_id
            )
        )  # type: ignore[return-value]

    async def routing_insights(
        self, *, tenant_id: UUID, project_id: UUID, state: str | None = None
    ) -> list[object]:
        return _dump(
            await self.experience.list_insights(
                tenant_id=tenant_id, project_id=project_id, state=state
            )
        )  # type: ignore[return-value]
