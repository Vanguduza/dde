"""Conversation/workspace checkpoints for Cursor-class Chat."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.frontend_chat_checkpoint import FrontendChatCheckpoint
from engine.contracts.frontend_conversation import FrontendConversation
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.studio.chat.activity import FrontendChatActivityService
from engine.studio.chat.attachments import FrontendChatAttachmentService
from engine.studio.chat.workspace_review import FrontendChatWorkspaceReviewService
from engine.studio.tables import (
    frontend_chat_checkpoints,
    frontend_conversation_turns,
    frontend_conversations,
)
from engine.truth.db import open_unit_of_work


def _context_hash(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class FrontendChatCheckpointService:
    """Sole writer of Chat checkpoints; never substitutes WorkerRun recovery."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        attachments: FrontendChatAttachmentService | None = None,
        workspace_review: FrontendChatWorkspaceReviewService | None = None,
        activities: FrontendChatActivityService | None = None,
    ) -> None:
        self._engine = engine
        self._attachments = attachments or FrontendChatAttachmentService(engine)
        self._workspace_review = workspace_review or FrontendChatWorkspaceReviewService(
            engine
        )
        self._activities = activities or FrontendChatActivityService(engine)

    async def create(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        created_by: UUID | None,
        note: str | None = None,
    ) -> FrontendChatCheckpoint:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            row = (
                (
                    await uow.connection.execute(
                        select(frontend_conversations).where(
                            frontend_conversations.c.conversation_id == conversation_id,
                            frontend_conversations.c.tenant_id == tenant_id,
                            frontend_conversations.c.project_id == project_id,
                            frontend_conversations.c.status == "OPEN",
                        )
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise DdeError(
                    "POLICY_DENIED", "unknown open Chat conversation", retryable=False
                )
            conversation = FrontendConversation.model_validate(dict(row))
            turn_sequence = int(
                await uow.connection.scalar(
                    select(
                        func.coalesce(
                            func.max(frontend_conversation_turns.c.sequence), 0
                        )
                    ).where(
                        frontend_conversation_turns.c.conversation_id == conversation_id
                    )
                )
                or 0
            )
        attachment_records = await self._attachments.list_for_conversation(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
        )
        attachment_refs = [
            item.attachment_id for item in attachment_records if item.status == "ACTIVE"
        ]
        workspace_revision: str | None = None
        diff_hash: str | None = None
        if conversation.active_workspace_id is not None:
            changes = await self._workspace_review.changes(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=conversation_id,
            )
            workspace_revision = changes.workspace_revision
            diff_hash = changes.diff_hash
        context_payload: dict[str, object] = {
            "conversation_id": str(conversation_id),
            "turn_sequence": turn_sequence,
            "mode": conversation.mode,
            "model_profile_id": conversation.model_profile_id,
            "plan_id": str(conversation.active_plan_id)
            if conversation.active_plan_id
            else None,
            "workspace_id": str(conversation.active_workspace_id)
            if conversation.active_workspace_id
            else None,
            "pinned_context_refs": list(conversation.pinned_context_refs),
            "attachment_refs": [str(item) for item in attachment_refs],
            "workspace_revision": workspace_revision,
            "diff_hash": diff_hash,
        }
        now = datetime.now(UTC)
        record = FrontendChatCheckpoint(
            checkpoint_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            turn_sequence=turn_sequence,
            mode=conversation.mode,
            model_profile_id=conversation.model_profile_id,
            plan_id=conversation.active_plan_id,
            workspace_id=conversation.active_workspace_id,
            pinned_context_refs=list(conversation.pinned_context_refs),
            attachment_refs=attachment_refs,
            workspace_revision=workspace_revision,
            diff_hash=diff_hash,
            context_hash=_context_hash(context_payload),
            note=note.strip() if note and note.strip() else None,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            await uow.connection.execute(
                frontend_chat_checkpoints.insert().values(
                    **record.model_dump(
                        exclude={"pinned_context_refs", "attachment_refs"}
                    ),
                    pinned_context_refs=list(record.pinned_context_refs),
                    attachment_refs=[str(item) for item in record.attachment_refs],
                )
            )
            await uow.commit()
        await self._activities.append(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            workspace_id=conversation.active_workspace_id,
            plan_id=conversation.active_plan_id,
            kind="CHECKPOINT_CREATED",
            state="COMPLETED",
            label="Chat checkpoint created",
            refs={
                "checkpoint_id": str(record.checkpoint_id),
                "context_hash": record.context_hash,
                "diff_hash": record.diff_hash,
            },
        )
        return record

    async def get(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        checkpoint_id: UUID,
    ) -> FrontendChatCheckpoint:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            row = (
                (
                    await uow.connection.execute(
                        select(frontend_chat_checkpoints).where(
                            frontend_chat_checkpoints.c.checkpoint_id == checkpoint_id,
                            frontend_chat_checkpoints.c.conversation_id
                            == conversation_id,
                            frontend_chat_checkpoints.c.tenant_id == tenant_id,
                            frontend_chat_checkpoints.c.project_id == project_id,
                        )
                    )
                )
                .mappings()
                .first()
            )
        if row is None:
            raise DdeError("POLICY_DENIED", "unknown Chat checkpoint", retryable=False)
        return FrontendChatCheckpoint.model_validate(dict(row))

    async def list_for_conversation(
        self, *, tenant_id: UUID, project_id: UUID, conversation_id: UUID
    ) -> tuple[FrontendChatCheckpoint, ...]:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            rows = (
                (
                    await uow.connection.execute(
                        select(frontend_chat_checkpoints)
                        .where(
                            frontend_chat_checkpoints.c.conversation_id
                            == conversation_id,
                            frontend_chat_checkpoints.c.tenant_id == tenant_id,
                            frontend_chat_checkpoints.c.project_id == project_id,
                        )
                        .order_by(frontend_chat_checkpoints.c.created_at.desc())
                    )
                )
                .mappings()
                .all()
            )
        return tuple(FrontendChatCheckpoint.model_validate(dict(row)) for row in rows)

    async def restore_context(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        checkpoint_id: UUID,
    ) -> FrontendConversation:
        """Restore conversational context only; never rewind workspace bytes."""
        checkpoint = await self.get(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            checkpoint_id=checkpoint_id,
        )
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                update(frontend_conversations)
                .where(
                    frontend_conversations.c.conversation_id == conversation_id,
                    frontend_conversations.c.tenant_id == tenant_id,
                    frontend_conversations.c.project_id == project_id,
                    frontend_conversations.c.status == "OPEN",
                )
                .values(
                    mode=checkpoint.mode,
                    model_profile_id=checkpoint.model_profile_id,
                    active_plan_id=checkpoint.plan_id,
                    active_workspace_id=checkpoint.workspace_id,
                    pinned_context_refs=list(checkpoint.pinned_context_refs),
                    lock_version=frontend_conversations.c.lock_version + 1,
                    updated_at=now,
                )
                .returning(frontend_conversations)
            )
            row = result.mappings().first()
            if row is None:
                raise DdeError(
                    "POLICY_DENIED", "unknown open Chat conversation", retryable=False
                )
            await uow.commit()
        conversation = FrontendConversation.model_validate(dict(row))
        await self._activities.append(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            workspace_id=conversation.active_workspace_id,
            plan_id=conversation.active_plan_id,
            kind="CHECKPOINT_RESTORED",
            state="COMPLETED",
            label="Restored Chat context checkpoint",
            refs={"checkpoint_id": str(checkpoint_id)},
        )
        return conversation
