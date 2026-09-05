"""DDE-069 Frontend Chat service.

Sole writer of `frontend_conversations` and
`frontend_conversation_turns`. Turns are append-only, and each records the
intent it was classified as, the context its references resolved against
and the ids of whatever it produced -- so the line from "make the hero
roomier" to the mutation that changed the hero is reconstructable later.

Routing is the point. A deterministic edit compiles to the same
`MutationRequest` the inspector produces and goes through the same
planner, locks and staleness checks. A design-class intent goes to the
DesignGateway. Neither path is special-cased, and there is no third path
that writes frontend state directly from chat.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.chat.activity import FrontendChatActivityService
from engine.chat.attachments import FrontendChatAttachmentService
from engine.chat.context_adapters import FrontendStudioChatContextAdapter
from engine.chat.context_manager import DdeConversationContextManager
from engine.chat.context_refs import FrontendChatContextService, parse_inline_refs
from engine.chat.intent import (
    DESIGN_INTENTS,
    ChatContext,
    Classification,
    Intent,
    classify,
)
from engine.chat.models import FrontendChatModelCatalog
from engine.chat.plans import FrontendChatPlanService
from engine.chat.tables import frontend_conversation_turns, frontend_conversations
from engine.contracts.frontend_conversation import FrontendConversation
from engine.contracts.frontend_conversation_turn import FrontendConversationTurn
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.fabric.lifecycle import FabricLifecycleService
from engine.fabric.runtime import AgentInteropRuntimeService
from engine.studio.audit.reads import ScreenAuditReadService
from engine.studio.design.gateway import DesignGateway
from engine.studio.inspector import InspectorService
from engine.studio.locks.service import LockService
from engine.studio.mutations.governed import GovernedMutationService
from engine.studio.mutations.planner import MutationRequest
from engine.studio.reads import FrontendReadService
from engine.truth.db import open_unit_of_work
from engine.workspaces.repository import WorkspaceRepository


@dataclass(frozen=True)
class TurnResult:
    """The persisted user turn plus the Studio reply rendered by the composer."""

    turn: FrontendConversationTurn
    reply: FrontendConversationTurn
    classification: Classification
    produced_refs: tuple[str, ...]
    message: str


class FrontendChatService:
    """The shared conversational control plane."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        mutations: GovernedMutationService | None = None,
        design: DesignGateway | None = None,
        reads: FrontendReadService | None = None,
        inspector: InspectorService | None = None,
        locks: LockService | None = None,
        attachments: FrontendChatAttachmentService | None = None,
        plans: FrontendChatPlanService | None = None,
        activities: FrontendChatActivityService | None = None,
        context: FrontendChatContextService | None = None,
        context_manager: DdeConversationContextManager | None = None,
        models: FrontendChatModelCatalog | None = None,
        fabric_runtime: AgentInteropRuntimeService | None = None,
        lifecycle: FabricLifecycleService | None = None,
        frontend_context: FrontendStudioChatContextAdapter | None = None,
        audit_reads: ScreenAuditReadService | None = None,
    ) -> None:
        self._engine = engine
        self._mutations = mutations or GovernedMutationService(engine)
        self._design = design or DesignGateway(engine)
        self._reads = reads or FrontendReadService(engine)
        self._inspector = inspector or InspectorService(engine)
        self._locks = locks or LockService(engine)
        self._activities = activities or FrontendChatActivityService(engine)
        self._attachments = attachments or FrontendChatAttachmentService(
            engine, activities=self._activities
        )
        self._plans = plans or FrontendChatPlanService(
            engine, activities=self._activities
        )
        self._context = context or FrontendChatContextService(
            engine, attachments=self._attachments, plans=self._plans
        )
        self._context_manager = context_manager or DdeConversationContextManager(
            engine, refs=self._context
        )
        self._models = models or FrontendChatModelCatalog()
        self._fabric_runtime = fabric_runtime or AgentInteropRuntimeService(engine)
        self._lifecycle = lifecycle or FabricLifecycleService(engine)
        self._frontend_context = frontend_context or FrontendStudioChatContextAdapter(
            engine, reads=self._reads, locks=self._locks
        )
        self._audit_reads = audit_reads or ScreenAuditReadService(engine)

    async def open(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID | None = None,
        screen_key: str | None = None,
        viewport: str = "desktop-1440",
        title: str | None = None,
        mode: str = "ASK",
        model_profile_id: str | None = None,
        active_workspace_id: UUID | None = None,
        context_domain: str | None = "DDE",
        active_task_id: UUID | None = None,
        active_worker_run_id: UUID | None = None,
        active_verification_run_id: UUID | None = None,
        active_artifact_ref: str | None = None,
        created_by: UUID | None = None,
        parent_conversation_id: UUID | None = None,
        branched_from_turn_id: UUID | None = None,
    ) -> FrontendConversation:
        if mode not in {"ASK", "PLAN", "EXECUTE"}:
            raise DdeError("VALIDATION_FAILED", "unknown Chat mode", retryable=False)
        selected_model = self._models.require_known(model_profile_id)
        if active_workspace_id is not None:
            await self._require_workspace(
                tenant_id=tenant_id,
                project_id=project_id,
                workspace_id=active_workspace_id,
            )
        now = datetime.now(UTC)
        record = FrontendConversation(
            conversation_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            active_candidate_id=None,
            design_session_id=None,
            screen_key=screen_key,
            selected_node_keys=[],
            viewport=viewport,
            title=title.strip() if title and title.strip() else None,
            status="OPEN",
            mode=mode,
            model_profile_id=selected_model,
            active_workspace_id=active_workspace_id,
            active_plan_id=None,
            context_domain=context_domain,
            active_task_id=active_task_id,
            active_worker_run_id=active_worker_run_id,
            active_verification_run_id=active_verification_run_id,
            active_artifact_ref=active_artifact_ref,
            parent_conversation_id=parent_conversation_id,
            branched_from_turn_id=branched_from_turn_id,
            pinned_context_refs=[],
            created_by=created_by,
            archived_at=None,
            lock_version=1,
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            await uow.connection.execute(
                frontend_conversations.insert().values(
                    **record.model_dump(
                        exclude={"selected_node_keys", "pinned_context_refs"}
                    ),
                    selected_node_keys=[],
                    pinned_context_refs=[],
                )
            )
            await uow.commit()
        return record

    async def set_context(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        selected_node_keys: list[str] | None = None,
        active_candidate_id: UUID | None = None,
        set_active_candidate: bool = False,
        screen_key: str | None = None,
        set_screen: bool = False,
        viewport: str | None = None,
        active_workspace_id: UUID | None = None,
        set_active_workspace: bool = False,
        context_domain: str | None = None,
        set_context_domain: bool = False,
        active_task_id: UUID | None = None,
        set_active_task: bool = False,
        active_worker_run_id: UUID | None = None,
        set_active_worker_run: bool = False,
        active_verification_run_id: UUID | None = None,
        set_active_verification_run: bool = False,
        active_artifact_ref: str | None = None,
        set_active_artifact: bool = False,
    ) -> FrontendConversation:
        """Update what the conversation is about.

        The selection lives on the conversation so a later turn saying
        "this" resolves to what the user actually had selected, rather
        than to whatever the client happened to send with that turn.
        """
        now = datetime.now(UTC)
        values: dict[str, object] = {"updated_at": now}
        if selected_node_keys is not None:
            values["selected_node_keys"] = selected_node_keys
        if set_active_candidate:
            values["active_candidate_id"] = active_candidate_id
        if set_screen:
            values["screen_key"] = screen_key
        if viewport is not None:
            values["viewport"] = viewport
        if set_active_workspace:
            if active_workspace_id is not None:
                await self._require_workspace(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    workspace_id=active_workspace_id,
                )
            values["active_workspace_id"] = active_workspace_id
        if set_context_domain:
            values["context_domain"] = context_domain
        if set_active_task:
            values["active_task_id"] = active_task_id
        if set_active_worker_run:
            values["active_worker_run_id"] = active_worker_run_id
        if set_active_verification_run:
            values["active_verification_run_id"] = active_verification_run_id
        if set_active_artifact:
            values["active_artifact_ref"] = active_artifact_ref
        values["lock_version"] = frontend_conversations.c.lock_version + 1
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                update(frontend_conversations)
                .where(
                    frontend_conversations.c.conversation_id == conversation_id,
                    frontend_conversations.c.tenant_id == tenant_id,
                    frontend_conversations.c.project_id == project_id,
                )
                .values(**values)
                .returning(frontend_conversations)
            )
            row = result.mappings().first()
            if row is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "unknown conversation in this project",
                    retryable=False,
                    details={"conversation_id": str(conversation_id)},
                )
            await uow.commit()
        return FrontendConversation.model_validate(dict(row))

    async def _require_workspace(
        self, *, tenant_id: UUID, project_id: UUID, workspace_id: UUID
    ) -> None:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            workspace = await WorkspaceRepository().get_workspace(
                uow.connection, workspace_id
            )
        if (
            workspace is None
            or workspace.tenant_id != tenant_id
            or workspace.project_id != project_id
        ):
            raise DdeError(
                "TENANT_SCOPE_VIOLATION",
                "workspace is outside Chat project scope",
                retryable=False,
            )
        if workspace.status not in {"READY", "IN_USE"}:
            raise DdeError(
                "WORKSPACE_UNAVAILABLE",
                "workspace is not available for Chat",
                retryable=False,
                details={"status": workspace.status},
            )

    async def get_conversation(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        conversation_id: UUID,
    ) -> FrontendConversation:
        item = await self._conversation(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
        )
        if item.mission_id != mission_id:
            raise DdeError(
                "TENANT_SCOPE_VIOLATION",
                "Chat conversation belongs to another mission",
                retryable=False,
            )
        return item

    async def list_conversations(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        include_archived: bool = False,
    ) -> tuple[FrontendConversation, ...]:
        conditions = [
            frontend_conversations.c.tenant_id == tenant_id,
            frontend_conversations.c.project_id == project_id,
            frontend_conversations.c.mission_id == mission_id,
        ]
        if not include_archived:
            conditions.append(frontend_conversations.c.status == "OPEN")
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            rows = (
                (
                    await uow.connection.execute(
                        select(frontend_conversations)
                        .where(*conditions)
                        .order_by(frontend_conversations.c.updated_at.desc())
                    )
                )
                .mappings()
                .all()
            )
        return tuple(FrontendConversation.model_validate(dict(row)) for row in rows)

    async def search_conversations(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        query: str,
    ) -> tuple[FrontendConversation, ...]:
        needle = query.strip()
        if not needle:
            return await self.list_conversations(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                include_archived=True,
            )
        pattern = f"%{needle.replace('%', r'\%').replace('_', r'\_')}%"
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            conversation_ids = select(
                frontend_conversation_turns.c.conversation_id
            ).where(
                frontend_conversation_turns.c.tenant_id == tenant_id,
                frontend_conversation_turns.c.project_id == project_id,
                frontend_conversation_turns.c.text.ilike(pattern, escape="\\"),
            )
            rows = (
                (
                    await uow.connection.execute(
                        select(frontend_conversations)
                        .where(
                            frontend_conversations.c.tenant_id == tenant_id,
                            frontend_conversations.c.project_id == project_id,
                            frontend_conversations.c.mission_id == mission_id,
                            (
                                frontend_conversations.c.title.ilike(
                                    pattern, escape="\\"
                                )
                                | frontend_conversations.c.conversation_id.in_(
                                    conversation_ids
                                )
                            ),
                        )
                        .order_by(frontend_conversations.c.updated_at.desc())
                    )
                )
                .mappings()
                .all()
            )
        return tuple(FrontendConversation.model_validate(dict(row)) for row in rows)

    async def rename(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        title: str,
    ) -> FrontendConversation:
        clean = title.strip()
        if not clean or len(clean) > 160:
            raise DdeError(
                "VALIDATION_FAILED",
                "Chat title must contain 1-160 characters",
                retryable=False,
            )
        return await self._update_conversation(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            values={"title": clean},
        )

    async def archive(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        archived: bool = True,
    ) -> FrontendConversation:
        return await self._update_conversation(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            values={
                "status": "ARCHIVED" if archived else "OPEN",
                "archived_at": datetime.now(UTC) if archived else None,
            },
            require_open=archived,
        )

    async def set_mode(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        mode: str,
    ) -> FrontendConversation:
        if mode not in {"ASK", "PLAN", "EXECUTE"}:
            raise DdeError("VALIDATION_FAILED", "unknown Chat mode", retryable=False)
        return await self._update_conversation(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            values={"mode": mode},
        )

    async def set_model(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        model_profile_id: str | None,
    ) -> FrontendConversation:
        selected = self._models.require_known(model_profile_id)
        return await self._update_conversation(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            values={"model_profile_id": selected},
        )

    async def pin_context(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        context_ref: str,
        pinned: bool,
    ) -> FrontendConversation:
        from engine.chat.context_refs import normalize_ref

        normalized = normalize_ref(context_ref)
        current = await self._conversation(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
        )
        refs = list(current.pinned_context_refs)
        if pinned and normalized not in refs:
            refs.append(normalized)
        if not pinned:
            refs = [item for item in refs if item != normalized]
        return await self._update_conversation(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            values={"pinned_context_refs": refs},
        )

    async def branch(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        from_turn_id: UUID | None,
        created_by: UUID | None,
        title: str | None = None,
    ) -> FrontendConversation:
        parent = await self._conversation(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
        )
        if from_turn_id is not None:
            async with open_unit_of_work(
                self._engine, tenant_id=tenant_id, project_id=project_id
            ) as uow:
                turn = await uow.connection.scalar(
                    select(frontend_conversation_turns.c.turn_id).where(
                        frontend_conversation_turns.c.turn_id == from_turn_id,
                        frontend_conversation_turns.c.conversation_id
                        == conversation_id,
                    )
                )
            if turn is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "branch turn does not belong to the source conversation",
                    retryable=False,
                )
        branched = await self.open(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=parent.mission_id,
            screen_key=parent.screen_key,
            viewport=parent.viewport,
            title=title or (f"{parent.title} — branch" if parent.title else "Branch"),
            mode=parent.mode,
            model_profile_id=parent.model_profile_id,
            active_workspace_id=parent.active_workspace_id,
            context_domain=parent.context_domain,
            active_task_id=parent.active_task_id,
            active_worker_run_id=parent.active_worker_run_id,
            active_verification_run_id=parent.active_verification_run_id,
            active_artifact_ref=parent.active_artifact_ref,
            created_by=created_by,
            parent_conversation_id=parent.conversation_id,
            branched_from_turn_id=from_turn_id,
        )
        return await self._update_conversation(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=branched.conversation_id,
            values={
                "active_candidate_id": parent.active_candidate_id,
                "pinned_context_refs": list(parent.pinned_context_refs),
            },
        )

    async def _update_conversation(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        values: dict[str, object],
        require_open: bool = True,
    ) -> FrontendConversation:
        now = datetime.now(UTC)
        conditions = [
            frontend_conversations.c.conversation_id == conversation_id,
            frontend_conversations.c.tenant_id == tenant_id,
            frontend_conversations.c.project_id == project_id,
        ]
        if require_open:
            conditions.append(frontend_conversations.c.status == "OPEN")
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            row = (
                (
                    await uow.connection.execute(
                        update(frontend_conversations)
                        .where(*conditions)
                        .values(
                            **values,
                            updated_at=now,
                            lock_version=frontend_conversations.c.lock_version + 1,
                        )
                        .returning(frontend_conversations)
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "unknown or inactive Chat conversation",
                    retryable=False,
                )
            await uow.commit()
        return FrontendConversation.model_validate(dict(row))

    async def send(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        text: str,
        attachment_ids: tuple[UUID, ...] = (),
        approval_id: UUID | None = None,
    ) -> TurnResult:
        """Classify a turn, enforce mode, route it, and persist exact lineage."""
        conversation = await self._conversation(
            tenant_id=tenant_id, project_id=project_id, conversation_id=conversation_id
        )
        if conversation.status != "OPEN":
            raise DdeError(
                "POLICY_DENIED",
                "archived Chat conversations are read-only",
                retryable=False,
            )
        await self._lifecycle.emit(
            tenant_id=tenant_id,
            project_id=project_id,
            event_kind="BEFORE_TURN",
            context={
                "conversation_id": str(conversation_id),
                "mode": conversation.mode,
                "model_profile_id": conversation.model_profile_id,
            },
            conversation_id=conversation_id,
        )
        attachments = await self._attachments.require_active_ids(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            attachment_ids=attachment_ids,
        )
        explicit_refs = parse_inline_refs(text)
        context_refs = tuple(
            dict.fromkeys(
                [
                    *conversation.pinned_context_refs,
                    *explicit_refs,
                    *(f"attachment:{item.attachment_id}" for item in attachments),
                ]
            )
        )
        await self._lifecycle.emit(
            tenant_id=tenant_id,
            project_id=project_id,
            event_kind="BEFORE_CONTEXT",
            context={
                "conversation_id": str(conversation_id),
                "requested_refs": list(context_refs),
            },
            conversation_id=conversation_id,
        )
        context = ChatContext(
            selected_node_keys=tuple(conversation.selected_node_keys),
            active_candidate_id=(
                str(conversation.active_candidate_id)
                if conversation.active_candidate_id
                else None
            ),
            screen_key=conversation.screen_key,
            viewport=conversation.viewport,
        )
        classification = classify(text, context)
        context_snapshot = await self._context_snapshot(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation=conversation,
        )
        managed_context = await self._context_manager.assemble_turn(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation=conversation,
            prompt=text,
            live_context=context_snapshot,
            explicit_refs=context_refs,
        )
        provider_context = managed_context.provider_payload()
        await self._lifecycle.emit(
            tenant_id=tenant_id,
            project_id=project_id,
            event_kind="AFTER_CONTEXT",
            context={
                "conversation_id": str(conversation_id),
                "context_snapshot_id": str(managed_context.context_snapshot_id),
                "included_refs": list(managed_context.explicit_context.included_refs),
                "memory_count": len(managed_context.memory_context.items),
                "history_turn_count": len(managed_context.history),
                "omitted_refs": list(managed_context.omitted_refs),
                "estimated_tokens": managed_context.used_tokens,
                "budget_tokens": managed_context.budget_tokens,
                "utilization": managed_context.utilization,
            },
            conversation_id=conversation_id,
        )
        context_snapshot.update(
            {
                "chat_mode": conversation.mode,
                "model_profile_id": conversation.model_profile_id,
                "active_workspace_id": (
                    str(conversation.active_workspace_id)
                    if conversation.active_workspace_id
                    else None
                ),
                "active_plan_id": (
                    str(conversation.active_plan_id)
                    if conversation.active_plan_id
                    else None
                ),
                "pinned_context_refs": list(conversation.pinned_context_refs),
                "inline_context_refs": list(explicit_refs),
                # Compatibility key consumed by the current Chat UI. The universal
                # allocator is authoritative and adds memory/history/token telemetry.
                "context_budget": provider_context["explicit_context"],
                "memory_context": provider_context["memory_context"],
                "history_context": provider_context["history"],
                "history_summary": provider_context["history_summary"],
                "token_management": provider_context["allocation"],
                "fabric_context_snapshot_id": provider_context["context_snapshot_id"],
                "compaction_snapshot_id": provider_context["compaction_snapshot_id"],
                "context_omitted_refs": provider_context["omitted_refs"],
                "context_omission_reasons": provider_context["omission_reasons"],
            }
        )
        await self._activities.append(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            kind="CONTEXT_ASSEMBLED",
            state="COMPLETED",
            label="Assembled universal DDE Chat context",
            refs={
                "context_snapshot_id": str(managed_context.context_snapshot_id),
                "compaction_snapshot_id": (
                    str(managed_context.compaction_snapshot_id)
                    if managed_context.compaction_snapshot_id
                    else None
                ),
                "included_refs": list(managed_context.explicit_context.included_refs),
                "memory_ids": [
                    str(item.memory_id) for item in managed_context.memory_context.items
                ],
                "omitted_refs": list(managed_context.omitted_refs),
                "estimated_tokens": managed_context.used_tokens,
                "budget_tokens": managed_context.budget_tokens,
                "utilization": managed_context.utilization,
            },
            workspace_id=conversation.active_workspace_id,
            plan_id=conversation.active_plan_id,
        )

        produced: tuple[str, ...] = ()
        outcome = "ANSWERED"
        refusal_code = classification.refusal_code
        refusal_detail = classification.refusal_detail
        message = ""
        turn_plan_id: UUID | None = None
        mutating_intents = {
            Intent.MUTATE_DETERMINISTIC,
            Intent.UNDO_REVERT,
            Intent.DESIGN_DIVERGENT,
            Intent.DESIGN_REFINE,
            Intent.LOCK_CHANGE,
            Intent.PROMOTE,
        }

        if refusal_code is not None:
            outcome = "REFUSED"
            message = refusal_detail or "the studio could not act on that"
        elif conversation.mode == "ASK" and classification.intent in mutating_intents:
            outcome = "REFUSED"
            refusal_code = "MODE_READ_ONLY"
            refusal_detail = (
                "Ask mode is read-only. Switch to Plan to prepare this change or "
                "Execute to run a governed operation."
            )
            message = refusal_detail
        elif conversation.mode == "PLAN" and classification.intent in mutating_intents:
            (
                outcome,
                refusal_code,
                refusal_detail,
                produced,
                message,
                turn_plan_id,
            ) = await self._route_plan(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation=conversation,
                classification=classification,
                text=text,
                context_snapshot=context_snapshot,
            )
        elif classification.intent is Intent.MUTATE_DETERMINISTIC:
            (
                outcome,
                refusal_code,
                refusal_detail,
                produced,
                message,
            ) = await self._route_mutation(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation=conversation,
                classification=classification,
            )
        elif classification.intent is Intent.UNDO_REVERT:
            (
                outcome,
                refusal_code,
                refusal_detail,
                produced,
                message,
            ) = await self._route_revert(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation=conversation,
            )
        elif classification.intent in DESIGN_INTENTS:
            (
                outcome,
                refusal_code,
                refusal_detail,
                produced,
                message,
            ) = await self._route_design(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation=conversation,
                classification=classification,
                text=text,
            )
        elif classification.intent in {
            Intent.COVERAGE_QUERY,
            Intent.QA_QUERY,
            Intent.INSPECT,
            Intent.SEARCH_SOURCE,
            Intent.EXPLAIN,
            Intent.LOCK_CHANGE,
            Intent.PROMOTE,
        }:
            (
                outcome,
                refusal_code,
                refusal_detail,
                message,
            ) = await self._route_read_or_explicit_action(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation=conversation,
                classification=classification,
            )
        else:
            (
                outcome,
                refusal_code,
                refusal_detail,
                produced,
                message,
            ) = await self._route_generative(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation=conversation,
                text=text,
                context_snapshot=context_snapshot,
                approval_id=approval_id,
            )

        user_turn = await self._append(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            role="user",
            text=text,
            classification=classification,
            outcome=outcome,
            refusal_code=refusal_code,
            refusal_detail=refusal_detail,
            produced=produced,
            context_snapshot=context_snapshot,
            attachment_ids=attachment_ids,
            plan_id=turn_plan_id,
            model_profile_id=conversation.model_profile_id,
        )
        await self._attachments.bind_to_turn(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            turn_id=user_turn.turn_id,
            attachment_ids=attachment_ids,
        )
        reply = await self._append(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            role="studio",
            text=message,
            classification=classification,
            outcome=outcome,
            refusal_code=refusal_code,
            refusal_detail=refusal_detail,
            produced=produced,
            context_snapshot=context_snapshot,
            attachment_ids=(),
            plan_id=turn_plan_id,
            model_profile_id=conversation.model_profile_id,
        )
        await self._lifecycle.emit(
            tenant_id=tenant_id,
            project_id=project_id,
            event_kind="AFTER_TURN",
            context={
                "conversation_id": str(conversation_id),
                "turn_id": str(user_turn.turn_id),
                "reply_turn_id": str(reply.turn_id),
                "intent": classification.intent.value,
                "outcome": outcome,
                "produced_refs": list(produced),
            },
            conversation_id=conversation_id,
        )
        return TurnResult(
            turn=user_turn,
            reply=reply,
            classification=classification,
            produced_refs=produced,
            message=message,
        )

    async def _route_generative(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation: FrontendConversation,
        text: str,
        context_snapshot: dict[str, object],
        approval_id: UUID | None,
    ) -> tuple[str, str | None, str | None, tuple[str, ...], str]:
        try:
            result = await self._fabric_runtime.invoke_conversation(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=conversation.conversation_id,
                prompt=text,
                context=context_snapshot,
                approval_id=approval_id,
            )
        except DdeError as exc:
            if exc.error_code == "APPROVAL_REQUIRED":
                invocation_id = (
                    exc.details.get("invocation_id") if exc.details else None
                )
                approval_refs: tuple[str, ...] = (
                    (f"provider_invocation:{invocation_id}",) if invocation_id else ()
                )
                return (
                    "REFUSED",
                    "APPROVAL_REQUIRED",
                    exc.message,
                    approval_refs,
                    exc.message,
                )
            if exc.error_code in {
                "CAPABILITY_UNAVAILABLE",
                "PROVIDER_ERROR",
                "PROVIDER_TIMEOUT",
                "WORKSPACE_UNAVAILABLE",
            }:
                return "REFUSED", "PROVIDER_UNAVAILABLE", exc.message, (), exc.message
            raise
        refs = (
            f"provider_invocation:{result.invocation.invocation_id}",
            f"worker_session:{result.session.worker_session_id}",
        )
        message = result.text.strip() or "Provider completed without assistant text."
        return "ANSWERED", None, None, refs, message

    def _provider_refusal(self, conversation: FrontendConversation) -> tuple[str, str]:
        option_id = conversation.model_profile_id or "AUTO"
        option = next(
            (item for item in self._models.options() if item.option_id == option_id),
            None,
        )
        if option is not None and option.status == "APPROVAL_REQUIRED":
            return (
                "APPROVAL_REQUIRED",
                f"{option.label} requires a fresh governed approval before "
                "model invocation. The user's turn is preserved and no provider "
                "call was made.",
            )
        reason = option.reason if option is not None else "selected provider is unknown"
        return (
            "PROVIDER_UNAVAILABLE",
            "No certified generative Chat provider is currently invokable for this "
            f"selection: {reason}",
        )

    async def _route_plan(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation: FrontendConversation,
        classification: Classification,
        text: str,
        context_snapshot: dict[str, object],
    ) -> tuple[str, str | None, str | None, tuple[str, ...], str, UUID | None]:
        if conversation.mission_id is None:
            detail = "Plan mode requires a mission-bound conversation"
            return "REFUSED", "CONTEXT_INCOMPLETE", detail, (), detail, None
        step: dict[str, object] | None = None
        if classification.intent is Intent.MUTATE_DETERMINISTIC:
            if (
                conversation.active_candidate_id is None
                or classification.mutation is None
            ):
                detail = (
                    "Plan edit requires an active candidate and deterministic mutation"
                )
                return "REFUSED", "CONTEXT_INCOMPLETE", detail, (), detail, None
            raw_payload = classification.mutation.get("payload")
            payload = dict(raw_payload) if isinstance(raw_payload, dict) else {}
            mutations = [
                {
                    "operation": str(classification.mutation["operation"]),
                    "target_key": key,
                    "origin": "CHAT",
                    "payload": payload,
                }
                for key in classification.target_keys
            ]
            step = {
                "title": "Apply governed frontend mutation",
                "description": text,
                "command_type": "frontend.mutation.apply",
                "target_type": "mission",
                "target_id": str(conversation.mission_id),
                "parameters": {
                    "candidate_id": str(conversation.active_candidate_id),
                    "mutations": mutations,
                },
                "depends_on": [],
            }
        elif classification.intent is Intent.UNDO_REVERT:
            if conversation.active_candidate_id is None:
                detail = "Plan undo requires an active candidate"
                return "REFUSED", "NO_ACTIVE_CANDIDATE", detail, (), detail, None
            history = await self._mutations.history(
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=conversation.active_candidate_id,
            )
            latest = next(
                (item for item in reversed(history) if item.status == "APPLIED"), None
            )
            if latest is None:
                detail = "the active candidate has no applied mutation to undo"
                return "REFUSED", "NOTHING_TO_REVERT", detail, (), detail, None
            step = {
                "title": f"Revert mutation {latest.sequence}",
                "description": text,
                "command_type": "frontend.mutation.revert",
                "target_type": "mission",
                "target_id": str(conversation.mission_id),
                "parameters": {
                    "candidate_id": str(conversation.active_candidate_id),
                    "mutation_id": str(latest.mutation_id),
                },
                "depends_on": [],
            }
        elif classification.intent in DESIGN_INTENTS:
            step = {
                "title": "Request governed design directions",
                "description": text,
                "command_type": "frontend.design.request",
                "target_type": "mission",
                "target_id": str(conversation.mission_id),
                "parameters": {
                    "conversation_id": str(conversation.conversation_id),
                    "scope_keys": list(classification.target_keys),
                    "instruction": text,
                    "direction_count": 3,
                },
                "depends_on": [],
            }
        else:
            detail = (
                "this action requires a separate explicit authority surface and is not "
                "admitted for Chat plan auto-execution"
            )
            return "REFUSED", "COMMAND_NOT_ALLOWED", detail, (), detail, None
        plan = await self._plans.create(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=conversation.mission_id,
            conversation_id=conversation.conversation_id,
            title="Chat plan",
            objective=text,
            steps=[step],
            approval_required=True,
            workspace_id=conversation.active_workspace_id,
            context_snapshot=context_snapshot,
        )
        return (
            "ROUTED",
            None,
            None,
            (str(plan.plan_id),),
            f"Plan created with {len(plan.steps)} step(s). Review and approve "
            "before execution.",
            plan.plan_id,
        )

    async def _route_mutation(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation: FrontendConversation,
        classification: Classification,
    ) -> tuple[str, str | None, str | None, tuple[str, ...], str]:
        if conversation.active_candidate_id is None:
            return (
                "REFUSED",
                "NO_ACTIVE_CANDIDATE",
                "chat edits apply to a candidate; none is active. The "
                "accepted design is never edited in place.",
                (),
                "no active candidate",
            )
        if classification.mutation is None:
            return (
                "REFUSED",
                "INTENT_AMBIGUOUS",
                "no deterministic mutation could be compiled from the message",
                (),
                "nothing to apply",
            )
        payload = classification.mutation["payload"]
        requests = [
            MutationRequest(
                operation=str(classification.mutation["operation"]),
                target_key=key,
                origin="CHAT",
                payload=dict(payload) if isinstance(payload, dict) else {},
            )
            for key in classification.target_keys
        ]
        governed = await self._mutations.apply(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=conversation.active_candidate_id,
            requests=requests,
            conversation_id=conversation.conversation_id,
        )
        result = governed.mutation
        produced = tuple(str(item.mutation_id) for item in result.applied)
        if result.applied and not result.refused:
            return (
                "ROUTED",
                None,
                None,
                produced,
                f"applied {len(result.applied)} change(s)",
            )
        if not result.applied:
            first = result.refused[0]
            return (
                "REFUSED",
                first.refusal_code,
                first.refusal_detail,
                (),
                first.refusal_detail or "refused",
            )
        first = result.refused[0]
        return (
            "ROUTED",
            first.refusal_code,
            first.refusal_detail,
            produced,
            f"applied {len(result.applied)}, refused {len(result.refused)}",
        )

    async def _route_read_or_explicit_action(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation: FrontendConversation,
        classification: Classification,
    ) -> tuple[str, str | None, str | None, str]:
        intent = classification.intent
        if intent is Intent.COVERAGE_QUERY:
            snapshot = await self._reads.snapshot(
                tenant_id=tenant_id, project_id=project_id
            )
            coverage = snapshot.coverage
            percent = (
                f"{round(coverage.weighted_percent)}%"
                if coverage.weighted_percent is not None
                else "percentage unavailable"
            )
            dimensions = ", ".join(
                f"{dimension}={state}" for dimension, state in coverage.dimension_states
            )
            message = (
                f"Coverage {coverage.summary_state}: {percent}; "
                f"blocking findings={coverage.blocking_finding_count}"
            )
            if dimensions:
                message += f"; dimensions: {dimensions}"
            if coverage.reason:
                message += f"; {coverage.reason}"
            return "ANSWERED", None, None, message

        if intent is Intent.QA_QUERY:
            pxg_key = (
                classification.target_keys[0] if classification.target_keys else None
            )
            findings = await self._audit_reads.current_findings(
                tenant_id=tenant_id, project_id=project_id, pxg_key=pxg_key
            )
            blocking = sum(1 for item in findings if item.severity == "BLOCKING")
            message = (
                f"Screen Audit: {len(findings)} unresolved finding(s); "
                f"blocking={blocking}"
            )
            if findings:
                message += "; " + " | ".join(
                    f"{item.finding_type}@{item.pxg_key or item.node_key or 'project'} "
                    f"[{item.severity}/{item.assessment_state}]"
                    for item in findings[:10]
                )
                if len(findings) > 10:
                    message += f"; +{len(findings) - 10} more"
            if conversation.active_candidate_id is not None:
                board = await self._reads.candidate_board(
                    tenant_id=tenant_id, project_id=project_id
                )
                candidate_id = str(conversation.active_candidate_id)
                card = next(
                    (item for item in board.cards if item.candidate_id == candidate_id),
                    None,
                )
                if card is not None:
                    run_state = card.verification_run_status or "NOT_EVALUATED"
                    message += f"; active candidate verification={run_state}"
            return "ANSWERED", None, None, message

        if intent is Intent.INSPECT:
            if conversation.active_candidate_id is None:
                detail = "inspection needs an active candidate; none is selected"
                return "REFUSED", "NO_ACTIVE_CANDIDATE", detail, detail
            if not classification.target_keys:
                detail = "inspection needs one stable selected PXG key"
                return "REFUSED", "AMBIGUOUS_REFERENCE", detail, detail
            descriptor = await self._inspector.describe(
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=conversation.active_candidate_id,
                pxg_key=classification.target_keys[0],
            )
            properties = ", ".join(item.property_name for item in descriptor.properties)
            verification = ", ".join(descriptor.required_verification)
            message = (
                f"{descriptor.title} ({descriptor.node_kind}); "
                f"candidate={descriptor.candidate_state}; "
                f"source={descriptor.source_mapping}"
            )
            if properties:
                message += f"; editable properties: {properties}"
            if verification:
                message += f"; required verification: {verification}"
            return "ANSWERED", None, None, message

        if intent is Intent.SEARCH_SOURCE:
            detail = (
                "Source Intelligence (DDE-069 M8) is not implemented; "
                "the studio will not fabricate source search results"
            )
            return "REFUSED", "CAPABILITY_UNAVAILABLE", detail, detail

        if intent is Intent.LOCK_CHANGE:
            detail = (
                "lock changes require the explicit governed lock control so creator/"
                "release authority is attributable; Chat will not invent that principal"
            )
            return "REFUSED", "EXPLICIT_CONTROL_REQUIRED", detail, detail

        if intent is Intent.PROMOTE:
            detail = (
                "promotion requires the explicit candidate promotion control and its "
                "complete gate decision; Chat will not bypass that acceptance surface"
            )
            return "REFUSED", "EXPLICIT_CONTROL_REQUIRED", detail, detail

        detail = (
            "no deterministic explanation binding exists for this wording; ask about "
            "coverage, QA, or a selected element instead"
        )
        return "REFUSED", "QUERY_UNSUPPORTED", detail, detail

    async def _route_revert(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation: FrontendConversation,
    ) -> tuple[str, str | None, str | None, tuple[str, ...], str]:
        if conversation.active_candidate_id is None:
            return (
                "REFUSED",
                "NO_ACTIVE_CANDIDATE",
                "undo applies to a candidate; none is active",
                (),
                "no active candidate to undo",
            )
        history = await self._mutations.history(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=conversation.active_candidate_id,
        )
        latest = next(
            (item for item in reversed(history) if item.status == "APPLIED"), None
        )
        if latest is None:
            return (
                "REFUSED",
                "NOTHING_TO_REVERT",
                "the active candidate has no applied mutation to undo",
                (),
                "nothing to undo",
            )
        reverted = await self._mutations.revert(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=conversation.active_candidate_id,
            mutation_id=latest.mutation_id,
            conversation_id=conversation.conversation_id,
        )
        produced = (str(reverted.compensating_mutation.mutation_id),)
        return (
            "ROUTED",
            None,
            None,
            produced,
            f"reverted mutation {latest.sequence}",
        )

    async def _route_design(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation: FrontendConversation,
        classification: Classification,
        text: str,
    ) -> tuple[str, str | None, str | None, tuple[str, ...], str]:
        """Design-class intents go to the gateway, which may refuse.

        A refusal here is surfaced verbatim rather than being softened
        into a generic failure: "no certified provider" and "the design
        system moved" call for different actions.
        """
        try:
            outcome = await self._design.request(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=conversation.mission_id,
                conversation_id=conversation.conversation_id,
                scope_keys=list(classification.target_keys),
                instruction=text,
            )
        except DdeError as exc:
            return (
                "REFUSED",
                exc.error_code,
                exc.message,
                (),
                exc.message,
            )
        produced = tuple(str(item.artifact_id) for item in outcome.usable)
        await self._link_session(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation.conversation_id,
            session_id=outcome.session.session_id,
        )
        return (
            "ROUTED",
            None,
            None,
            produced,
            f"{len(produced)} direction(s) generated",
        )

    async def _link_session(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        session_id: UUID,
    ) -> None:
        """One conversation, one active design session — not a second chat."""
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            await uow.connection.execute(
                update(frontend_conversations)
                .where(frontend_conversations.c.conversation_id == conversation_id)
                .values(design_session_id=session_id, updated_at=now)
            )
            await uow.commit()

    async def _conversation(
        self, *, tenant_id: UUID, project_id: UUID, conversation_id: UUID
    ) -> FrontendConversation:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                select(frontend_conversations).where(
                    frontend_conversations.c.conversation_id == conversation_id,
                    frontend_conversations.c.tenant_id == tenant_id,
                    frontend_conversations.c.project_id == project_id,
                )
            )
            row = result.mappings().first()
        if row is None:
            raise DdeError(
                "POLICY_DENIED",
                "unknown conversation in this project",
                retryable=False,
                details={"conversation_id": str(conversation_id)},
            )
        return FrontendConversation.model_validate(dict(row))

    async def _append(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        role: str,
        text: str,
        classification: Classification,
        outcome: str,
        refusal_code: str | None,
        refusal_detail: str | None,
        produced: tuple[str, ...],
        context_snapshot: dict[str, object],
        attachment_ids: tuple[UUID, ...],
        plan_id: UUID | None,
        model_profile_id: str | None,
    ) -> FrontendConversationTurn:
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            locked = await uow.connection.scalar(
                select(frontend_conversations.c.conversation_id)
                .where(
                    frontend_conversations.c.conversation_id == conversation_id,
                    frontend_conversations.c.tenant_id == tenant_id,
                    frontend_conversations.c.project_id == project_id,
                )
                .with_for_update()
            )
            if locked is None:
                raise DdeError(
                    "POLICY_DENIED", "unknown Chat conversation", retryable=False
                )
            sequence = (
                int(
                    await uow.connection.scalar(
                        select(
                            func.coalesce(
                                func.max(frontend_conversation_turns.c.sequence), 0
                            )
                        ).where(
                            frontend_conversation_turns.c.conversation_id
                            == conversation_id
                        )
                    )
                    or 0
                )
                + 1
            )
            record = FrontendConversationTurn(
                turn_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=conversation_id,
                sequence=sequence,
                role=role,
                text=text,
                intent=classification.intent.value,
                outcome=outcome,
                refusal_code=refusal_code,
                refusal_detail=refusal_detail,
                resolved_context={
                    "target_keys": list(classification.target_keys),
                    "references": dict(classification.references),
                    "context": context_snapshot,
                },
                produced_refs=list(produced),
                attachment_ids=list(attachment_ids),
                plan_id=plan_id,
                model_profile_id=model_profile_id,
                created_at=now,
                updated_at=now,
            )
            await uow.connection.execute(
                frontend_conversation_turns.insert().values(
                    **record.model_dump(
                        exclude={
                            "resolved_context",
                            "produced_refs",
                            "attachment_ids",
                        }
                    ),
                    resolved_context=record.resolved_context,
                    produced_refs=list(produced),
                    attachment_ids=[str(item) for item in attachment_ids],
                )
            )
            await uow.commit()
        return record

    async def _context_snapshot(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation: FrontendConversation,
    ) -> dict[str, object]:
        """Resolve authority-owned universal context for one turn.

        Generic DDE identity is always present. Domain-specific adapters enrich
        it only when that domain is active; a mission/task conversation therefore
        does not need PXG, Contract or candidate state to exist.
        """
        context: dict[str, object] = {
            "project_id": str(project_id),
            "mission_id": str(conversation.mission_id)
            if conversation.mission_id
            else None,
            "context_domain": conversation.context_domain or "DDE",
            "active_task_id": str(conversation.active_task_id)
            if conversation.active_task_id
            else None,
            "active_workspace_id": str(conversation.active_workspace_id)
            if conversation.active_workspace_id
            else None,
            "active_worker_run_id": str(conversation.active_worker_run_id)
            if conversation.active_worker_run_id
            else None,
            "active_worker_session_id": str(conversation.active_worker_session_id)
            if conversation.active_worker_session_id
            else None,
            "active_verification_run_id": str(conversation.active_verification_run_id)
            if conversation.active_verification_run_id
            else None,
            "active_artifact_ref": conversation.active_artifact_ref,
            "pinned_context_refs": list(conversation.pinned_context_refs),
        }
        legacy_frontend = conversation.context_domain is None and any(
            (
                conversation.screen_key,
                conversation.active_candidate_id,
                conversation.design_session_id,
                conversation.selected_node_keys,
            )
        )
        if conversation.context_domain == "FRONTEND_STUDIO" or legacy_frontend:
            frontend = await self._frontend_context.snapshot(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation=conversation,
            )
            context["frontend_studio"] = frontend
            # Preserve the DDE-069 turn lineage shape for compatibility while
            # consumers migrate to the namespaced adapter payload.
            context.update(frontend)
        return context

    async def latest_for_mission(
        self, *, tenant_id: UUID, project_id: UUID, mission_id: UUID
    ) -> FrontendConversation | None:
        """Return the durable conversation a mission should reopen after reload."""
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            row = (
                (
                    await uow.connection.execute(
                        select(frontend_conversations)
                        .where(
                            frontend_conversations.c.tenant_id == tenant_id,
                            frontend_conversations.c.project_id == project_id,
                            frontend_conversations.c.mission_id == mission_id,
                            frontend_conversations.c.status == "OPEN",
                        )
                        .order_by(frontend_conversations.c.updated_at.desc())
                        .limit(1)
                    )
                )
                .mappings()
                .first()
            )
        return FrontendConversation.model_validate(dict(row)) if row else None

    async def history(
        self, *, tenant_id: UUID, project_id: UUID, conversation_id: UUID
    ) -> tuple[FrontendConversationTurn, ...]:
        """Visible history including immutable parent lineage for branches."""
        conversation = await self._conversation(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
        )
        own = await self._direct_history(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
        )
        if conversation.parent_conversation_id is None:
            return own
        parent_history = await self.history(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation.parent_conversation_id,
        )
        if conversation.branched_from_turn_id is not None:
            direct_parent = await self._direct_history(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=conversation.parent_conversation_id,
            )
            branch_turn = next(
                (
                    item
                    for item in direct_parent
                    if item.turn_id == conversation.branched_from_turn_id
                ),
                None,
            )
            if branch_turn is None:
                raise DdeError(
                    "CONTEXT_INCOMPLETE",
                    "Chat branch lineage points to a missing parent turn",
                    retryable=False,
                )
            parent_history = tuple(
                item
                for item in parent_history
                if item.conversation_id != conversation.parent_conversation_id
                or item.sequence <= branch_turn.sequence
            )
        return (*parent_history, *own)

    async def _direct_history(
        self, *, tenant_id: UUID, project_id: UUID, conversation_id: UUID
    ) -> tuple[FrontendConversationTurn, ...]:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                select(frontend_conversation_turns)
                .where(
                    frontend_conversation_turns.c.conversation_id == conversation_id,
                    frontend_conversation_turns.c.tenant_id == tenant_id,
                    frontend_conversation_turns.c.project_id == project_id,
                )
                .order_by(frontend_conversation_turns.c.sequence)
            )
            rows = result.mappings().all()
        return tuple(FrontendConversationTurn.model_validate(dict(row)) for row in rows)
