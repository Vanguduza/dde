"""Append-only Cursor-class Chat activity timeline."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.frontend_chat_activity import FrontendChatActivity
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.studio.tables import frontend_chat_activities, frontend_conversations
from engine.truth.db import open_unit_of_work


class FrontendChatActivityService:
    """Sole writer of the operator-visible chat activity stream."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def append(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        kind: str,
        state: str,
        label: str,
        detail: str | None = None,
        refs: dict[str, object] | None = None,
        cancellable: bool = False,
        turn_id: UUID | None = None,
        plan_id: UUID | None = None,
        workspace_id: UUID | None = None,
        command_id: UUID | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> FrontendChatActivity:
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            # Serialize sequence allocation on the conversation row. A plain
            # max(sequence)+1 can duplicate under two simultaneous tool calls.
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
                    "POLICY_DENIED",
                    "unknown Chat conversation in this project",
                    retryable=False,
                )
            sequence = (
                int(
                    await uow.connection.scalar(
                        select(
                            func.coalesce(
                                func.max(frontend_chat_activities.c.sequence), 0
                            )
                        ).where(
                            frontend_chat_activities.c.conversation_id
                            == conversation_id
                        )
                    )
                    or 0
                )
                + 1
            )
            record = FrontendChatActivity(
                activity_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=conversation_id,
                sequence=sequence,
                turn_id=turn_id,
                plan_id=plan_id,
                workspace_id=workspace_id,
                command_id=command_id,
                kind=kind,
                state=state,
                label=label,
                detail=detail,
                refs=refs or {},
                cancellable=cancellable,
                cancel_reason=None,
                started_at=started_at,
                completed_at=completed_at,
                created_at=now,
                updated_at=now,
            )
            await uow.connection.execute(
                frontend_chat_activities.insert().values(
                    **record.model_dump(exclude={"refs"}), refs=record.refs
                )
            )
            await uow.commit()
        return record

    async def list_for_conversation(
        self, *, tenant_id: UUID, project_id: UUID, conversation_id: UUID
    ) -> tuple[FrontendChatActivity, ...]:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            rows = (
                (
                    await uow.connection.execute(
                        select(frontend_chat_activities)
                        .where(
                            frontend_chat_activities.c.conversation_id
                            == conversation_id,
                            frontend_chat_activities.c.tenant_id == tenant_id,
                            frontend_chat_activities.c.project_id == project_id,
                        )
                        .order_by(frontend_chat_activities.c.sequence)
                    )
                )
                .mappings()
                .all()
            )
        return tuple(FrontendChatActivity.model_validate(dict(row)) for row in rows)

    async def cancel(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        activity_id: UUID,
        reason: str,
    ) -> FrontendChatActivity:
        if not reason.strip():
            raise DdeError(
                "VALIDATION_FAILED", "cancel reason is required", retryable=False
            )
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            row = (
                (
                    await uow.connection.execute(
                        select(frontend_chat_activities)
                        .where(
                            frontend_chat_activities.c.activity_id == activity_id,
                            frontend_chat_activities.c.conversation_id
                            == conversation_id,
                            frontend_chat_activities.c.tenant_id == tenant_id,
                            frontend_chat_activities.c.project_id == project_id,
                        )
                        .with_for_update()
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise DdeError(
                    "POLICY_DENIED", "unknown Chat activity", retryable=False
                )
            current = FrontendChatActivity.model_validate(dict(row))
            if not current.cancellable or current.state not in {"PENDING", "RUNNING"}:
                raise DdeError(
                    "ACTIVITY_NOT_CANCELLABLE",
                    "activity is not currently cancellable",
                    retryable=False,
                    details={
                        "state": current.state,
                        "cancellable": current.cancellable,
                    },
                )
            await uow.connection.execute(
                update(frontend_chat_activities)
                .where(frontend_chat_activities.c.activity_id == activity_id)
                .values(
                    state="CANCELLED",
                    cancellable=False,
                    cancel_reason=reason.strip(),
                    completed_at=now,
                    updated_at=now,
                )
            )
            updated = (
                (
                    await uow.connection.execute(
                        select(frontend_chat_activities).where(
                            frontend_chat_activities.c.activity_id == activity_id
                        )
                    )
                )
                .mappings()
                .one()
            )
            await uow.commit()
        return FrontendChatActivity.model_validate(dict(updated))
