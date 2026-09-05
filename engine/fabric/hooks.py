"""Governed lifecycle hooks that emit proposals, never direct side effects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.ai_hook import AiHook
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.fabric.automations import condition_matches
from engine.fabric.repository import FabricRepository
from engine.fabric.tables import ai_hooks


@dataclass(frozen=True)
class HookProposal:
    hook_id: UUID
    event_kind: str
    action_kind: str
    action_payload: dict[str, object]


class HookService:
    def __init__(self, engine: AsyncEngine) -> None:
        self.repo = FabricRepository(engine)

    async def create(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        name: str,
        event_kind: str,
        action_kind: str,
        condition: dict[str, object],
        action_payload: dict[str, object],
        conversation_id: UUID | None = None,
        created_by: UUID | None = None,
    ) -> AiHook:
        if not name.strip():
            raise DdeError("VALIDATION_FAILED", "hook name is required")
        # A proposed command needs an exact structured command; it still
        # re-enters Gateway later.
        if action_kind == "PROPOSE_COMMAND":
            if not isinstance(
                action_payload.get("command_type"), str
            ) or not isinstance(action_payload.get("parameters"), dict):
                raise DdeError(
                    "VALIDATION_FAILED",
                    "command hook requires command_type and parameters",
                )
        now = datetime.now(UTC)
        values: dict[str, object] = {
            "hook_id": uuid7(),
            "tenant_id": tenant_id,
            "project_id": project_id,
            "conversation_id": conversation_id,
            "name": name.strip(),
            "event_kind": event_kind,
            "action_kind": action_kind,
            "condition": condition,
            "action_payload": action_payload,
            "state": "ACTIVE",
            "last_triggered_at": None,
            "trigger_count": 0,
            "created_by": created_by,
            "lock_version": 1,
            "created_at": now,
            "updated_at": now,
        }
        AiHook.model_validate(values)
        return await self.repo.insert_model(
            table=ai_hooks,
            model=AiHook,
            tenant_id=tenant_id,
            project_id=project_id,
            values=values,
        )

    async def evaluate(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        event_kind: str,
        context: dict[str, object],
        conversation_id: UUID | None = None,
    ) -> tuple[HookProposal, ...]:
        rows = await self.repo.list_models(
            table=ai_hooks,
            model=AiHook,
            tenant_id=tenant_id,
            project_id=project_id,
            filters={"event_kind": event_kind, "state": "ACTIVE"},
            order_by=(ai_hooks.c.created_at.asc(),),
            limit=500,
        )
        proposals = []
        for hook in rows:
            if (
                hook.conversation_id is not None
                and hook.conversation_id != conversation_id
            ):
                continue
            if hook.condition and not condition_matches(hook.condition, context):
                continue
            proposals.append(
                HookProposal(
                    hook.hook_id, hook.event_kind, hook.action_kind, hook.action_payload
                )
            )
        return tuple(proposals)

    async def record_trigger(
        self, *, tenant_id: UUID, project_id: UUID, hook_id: UUID, lock_version: int
    ) -> AiHook:
        hook = await self.get(
            tenant_id=tenant_id, project_id=project_id, hook_id=hook_id
        )
        if hook.state != "ACTIVE":
            raise DdeError("VERSION_CONFLICT", "inactive hook cannot record a trigger")
        now = datetime.now(UTC)
        return await self.repo.update_locked(
            table=ai_hooks,
            model=AiHook,
            id_column="hook_id",
            object_id=hook_id,
            tenant_id=tenant_id,
            project_id=project_id,
            lock_version=lock_version,
            values={
                "last_triggered_at": now,
                "trigger_count": hook.trigger_count + 1,
                "updated_at": now,
            },
        )

    async def set_state(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        hook_id: UUID,
        lock_version: int,
        state: str,
    ) -> AiHook:
        hook = await self.get(
            tenant_id=tenant_id, project_id=project_id, hook_id=hook_id
        )
        legal = {
            "ACTIVE": {"PAUSED", "DISABLED"},
            "PAUSED": {"ACTIVE", "DISABLED"},
            "DISABLED": set(),
        }
        if state not in legal[hook.state]:
            raise DdeError("VERSION_CONFLICT", "illegal hook state transition")
        return await self.repo.update_locked(
            table=ai_hooks,
            model=AiHook,
            id_column="hook_id",
            object_id=hook_id,
            tenant_id=tenant_id,
            project_id=project_id,
            lock_version=lock_version,
            values={"state": state, "updated_at": datetime.now(UTC)},
        )

    async def get(self, *, tenant_id: UUID, project_id: UUID, hook_id: UUID) -> AiHook:
        return await self.repo.get_model(
            table=ai_hooks,
            model=AiHook,
            id_column="hook_id",
            object_id=hook_id,
            tenant_id=tenant_id,
            project_id=project_id,
        )

    async def list_hooks(
        self, *, tenant_id: UUID, project_id: UUID, conversation_id: UUID | None = None
    ) -> tuple[AiHook, ...]:
        rows = await self.repo.list_models(
            table=ai_hooks,
            model=AiHook,
            tenant_id=tenant_id,
            project_id=project_id,
            order_by=(ai_hooks.c.created_at.asc(),),
        )
        if conversation_id is None:
            return rows
        return tuple(
            row for row in rows if row.conversation_id in {None, conversation_id}
        )
