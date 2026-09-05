"""Execute the safe, proposal-only consequences of Fabric lifecycle hooks."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.chat.activity import FrontendChatActivityService
from engine.chat.checkpoints import FrontendChatCheckpointService
from engine.core.errors import DdeError
from engine.fabric.hooks import HookProposal, HookService
from engine.fabric.memory import MemoryService
from engine.fabric.skills import SkillService


@dataclass(frozen=True)
class LifecycleEmission:
    event_kind: str
    proposal_refs: tuple[str, ...]


class FabricLifecycleService:
    """Evaluate hooks and materialize only non-sovereign hook actions.

    PROPOSE_COMMAND and RUN_SKILL become visible proposals; they never execute
    directly here. Mutating work must re-enter Gateway/plan authority.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self.hooks = HookService(engine)
        self.memory = MemoryService(engine)
        self.skills = SkillService(engine)
        self.activities = FrontendChatActivityService(engine)
        self.checkpoints = FrontendChatCheckpointService(engine)

    async def emit(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        event_kind: str,
        context: dict[str, object],
        conversation_id: UUID | None = None,
        principal_id: UUID | None = None,
    ) -> LifecycleEmission:
        proposals = await self.hooks.evaluate(
            tenant_id=tenant_id,
            project_id=project_id,
            event_kind=event_kind,
            context=context,
            conversation_id=conversation_id,
        )
        refs: list[str] = []
        for proposal in proposals:
            hook = await self.hooks.get(
                tenant_id=tenant_id,
                project_id=project_id,
                hook_id=proposal.hook_id,
            )
            await self.hooks.record_trigger(
                tenant_id=tenant_id,
                project_id=project_id,
                hook_id=hook.hook_id,
                lock_version=hook.lock_version,
            )
            ref = await self._materialize(
                proposal,
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=conversation_id,
                principal_id=principal_id,
                context=context,
            )
            if ref:
                refs.append(ref)
        return LifecycleEmission(event_kind=event_kind, proposal_refs=tuple(refs))

    async def _materialize(
        self,
        proposal: HookProposal,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID | None,
        principal_id: UUID | None,
        context: dict[str, object],
    ) -> str | None:
        payload = proposal.action_payload
        if proposal.action_kind == "RECORD_ACTIVITY":
            if conversation_id is None:
                return None
            activity = await self.activities.append(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=conversation_id,
                kind="STATUS",
                state="COMPLETED",
                label=str(payload.get("label") or f"Hook {proposal.event_kind}"),
                detail=str(payload.get("detail")) if payload.get("detail") else None,
                refs={"hook_id": str(proposal.hook_id), "context": context},
            )
            return f"chat_activity:{activity.activity_id}"
        if proposal.action_kind == "CREATE_CHECKPOINT":
            if conversation_id is None:
                return None
            checkpoint = await self.checkpoints.create(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=conversation_id,
                created_by=principal_id,
                note=str(payload.get("note") or f"Hook {proposal.event_kind}"),
            )
            return f"chat_checkpoint:{checkpoint.checkpoint_id}"
        if proposal.action_kind == "PROPOSE_MEMORY":
            scope_kind = str(payload.get("scope_kind") or "CONVERSATION")
            scope_ref = str(payload.get("scope_ref") or conversation_id or project_id)
            content = payload.get("content")
            if not isinstance(content, str) or not content.strip():
                raise DdeError(
                    "VALIDATION_FAILED", "PROPOSE_MEMORY hook requires content"
                )
            memory = await self.memory.propose(
                tenant_id=tenant_id,
                project_id=project_id,
                scope_kind=scope_kind,
                scope_ref=scope_ref,
                content=content,
                source_type="HOOK",
                source_refs=[f"hook:{proposal.hook_id}"],
                trust_class="ADVISORY",
                metadata={"event_kind": proposal.event_kind},
            )
            return f"memory:{memory.memory_id}"
        if proposal.action_kind == "RUN_SKILL":
            skill_raw = payload.get("skill_id")
            if not isinstance(skill_raw, str):
                raise DdeError("VALIDATION_FAILED", "RUN_SKILL hook requires skill_id")
            try:
                skill_id = UUID(skill_raw)
            except ValueError as exc:
                raise DdeError(
                    "VALIDATION_FAILED", "hook skill_id must be UUID"
                ) from exc
            skill = await self.skills.get(
                tenant_id=tenant_id, project_id=project_id, skill_id=skill_id
            )
            if skill.status != "CERTIFIED":
                raise DdeError(
                    "CAPABILITY_UNAVAILABLE",
                    "hook cannot propose execution of an uncertified skill",
                )
            return f"skill_proposal:{skill.skill_id}"
        if proposal.action_kind == "PROPOSE_COMMAND":
            command_type = payload.get("command_type")
            if not isinstance(command_type, str):
                raise DdeError(
                    "VALIDATION_FAILED", "PROPOSE_COMMAND hook lacks command_type"
                )
            return f"command_proposal:{proposal.hook_id}:{command_type}"
        raise DdeError(
            "VALIDATION_FAILED",
            "unknown hook action kind",
            details={"action_kind": proposal.action_kind},
        )
