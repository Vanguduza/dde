"""Bind Fabric policy/session identity onto a durable DDE conversation."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.ai_conversation_policy import AiConversationPolicy
from engine.contracts.frontend_conversation import FrontendConversation
from engine.contracts.worker_session import WorkerSession
from engine.core.errors import DdeError
from engine.fabric.repository import FabricRepository
from engine.fabric.tables import ai_conversation_policies, worker_sessions
from engine.studio.tables import frontend_conversations
from engine.truth.db import open_unit_of_work


class ConversationFabricBindingService:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self.repo = FabricRepository(engine)

    async def bind_policy(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        policy_id: UUID | None,
        lock_version: int,
    ) -> FrontendConversation:
        if policy_id is not None:
            await self.repo.get_model(
                table=ai_conversation_policies,
                model=AiConversationPolicy,
                id_column="policy_id",
                object_id=policy_id,
                tenant_id=tenant_id,
                project_id=project_id,
            )
        return await self._update(
            tenant_id, project_id, conversation_id, lock_version, policy_id=policy_id
        )

    async def bind_session(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        worker_session_id: UUID | None,
        lock_version: int,
    ) -> FrontendConversation:
        if worker_session_id is not None:
            session = await self.repo.get_model(
                table=worker_sessions,
                model=WorkerSession,
                id_column="worker_session_id",
                object_id=worker_session_id,
                tenant_id=tenant_id,
                project_id=project_id,
            )
            if session.state in {"FAILED", "CLOSED"}:
                raise DdeError(
                    "VERSION_CONFLICT", "terminal WorkerSession cannot be bound to Chat"
                )
        return await self._update(
            tenant_id,
            project_id,
            conversation_id,
            lock_version,
            active_worker_session_id=worker_session_id,
        )

    async def _update(
        self,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        lock_version: int,
        **values: object,
    ) -> FrontendConversation:
        async with open_unit_of_work(
            self.engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                update(frontend_conversations)
                .where(
                    frontend_conversations.c.conversation_id == conversation_id,
                    frontend_conversations.c.tenant_id == tenant_id,
                    frontend_conversations.c.project_id == project_id,
                    frontend_conversations.c.lock_version == lock_version,
                )
                .values(
                    **values,
                    updated_at=datetime.now(UTC),
                    lock_version=frontend_conversations.c.lock_version + 1,
                )
                .returning(frontend_conversations)
            )
            row = result.mappings().one_or_none()
            if row is None:
                exists = await uow.connection.scalar(
                    select(frontend_conversations.c.conversation_id).where(
                        frontend_conversations.c.conversation_id == conversation_id,
                        frontend_conversations.c.tenant_id == tenant_id,
                        frontend_conversations.c.project_id == project_id,
                    )
                )
                raise DdeError(
                    "VERSION_CONFLICT" if exists else "POLICY_DENIED",
                    "conversation changed concurrently"
                    if exists
                    else "unknown conversation",
                )
            await uow.commit()
        return FrontendConversation.model_validate(dict(row))
