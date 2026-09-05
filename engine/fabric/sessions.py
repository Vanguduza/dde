"""Durable WorkerSession lifecycle for provider/harness federation."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.agent_interop_endpoint import AgentInteropEndpoint
from engine.contracts.worker_session import WorkerSession
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.fabric.repository import FabricRepository
from engine.fabric.tables import agent_interop_endpoints, worker_sessions

_TRANSITIONS: dict[str, frozenset[str]] = {
    "OPENING": frozenset({"ACTIVE", "FAILED", "CLOSED"}),
    "ACTIVE": frozenset({"PAUSED", "DETACHED", "FAILED", "CLOSED"}),
    "PAUSED": frozenset({"RESUMING", "FAILED", "CLOSED"}),
    "DETACHED": frozenset({"RESUMING", "FAILED", "CLOSED"}),
    "RESUMING": frozenset({"ACTIVE", "FAILED", "CLOSED"}),
    "FAILED": frozenset({"RESUMING", "CLOSED"}),
    "CLOSED": frozenset(),
}


def session_config_hash(config: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


class WorkerSessionService:
    def __init__(self, engine: AsyncEngine) -> None:
        self.repo = FabricRepository(engine)

    async def open(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        endpoint_id: UUID,
        mission_id: UUID | None = None,
        task_id: UUID | None = None,
        worker_profile_id: str | None = None,
        requested_model_id: str | None = None,
        workspace_id: UUID | None = None,
        context_package_hash: str | None = None,
        tool_policy_hash: str | None = None,
        session_config: dict[str, object] | None = None,
        parent_session_id: UUID | None = None,
        forked_from_session_id: UUID | None = None,
    ) -> WorkerSession:
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
                "provider session cannot open on an uncertified interop endpoint",
                retryable=False,
                details={
                    "endpoint_id": str(endpoint_id),
                    "certification_state": endpoint.certification_state,
                },
            )
        if endpoint.health_state not in {"HEALTHY", "DEGRADED"}:
            raise DdeError(
                "CAPABILITY_UNAVAILABLE",
                "provider endpoint is not healthy enough to open a session",
                retryable=True,
                details={"health_state": endpoint.health_state},
            )
        now = datetime.now(UTC)
        values = {
            "worker_session_id": uuid7(),
            "tenant_id": tenant_id,
            "project_id": project_id,
            "mission_id": mission_id,
            "task_id": task_id,
            "endpoint_id": endpoint_id,
            "worker_profile_id": worker_profile_id,
            "provider_session_ref": None,
            "requested_model_id": requested_model_id,
            "serving_model_id": None,
            "workspace_id": workspace_id,
            "state": "OPENING",
            "capability_snapshot": endpoint.certified_capabilities,
            "context_package_hash": context_package_hash,
            "tool_policy_hash": tool_policy_hash,
            "session_config_hash": session_config_hash(session_config or {}),
            "parent_session_id": parent_session_id,
            "forked_from_session_id": forked_from_session_id,
            "last_error": None,
            "lock_version": 1,
            "created_at": now,
            "last_activity_at": now,
            "updated_at": now,
        }
        WorkerSession.model_validate(values)
        return await self.repo.insert_model(
            table=worker_sessions,
            model=WorkerSession,
            tenant_id=tenant_id,
            project_id=project_id,
            values=values,
        )

    async def get(
        self, *, tenant_id: UUID, project_id: UUID, worker_session_id: UUID
    ) -> WorkerSession:
        return await self.repo.get_model(
            table=worker_sessions,
            model=WorkerSession,
            id_column="worker_session_id",
            object_id=worker_session_id,
            tenant_id=tenant_id,
            project_id=project_id,
        )

    async def list_sessions(
        self, *, tenant_id: UUID, project_id: UUID, state: str | None = None
    ) -> tuple[WorkerSession, ...]:
        return await self.repo.list_models(
            table=worker_sessions,
            model=WorkerSession,
            tenant_id=tenant_id,
            project_id=project_id,
            filters={"state": state} if state else None,
            order_by=(worker_sessions.c.last_activity_at.desc(),),
        )

    async def activate(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        worker_session_id: UUID,
        lock_version: int,
        provider_session_ref: str,
        serving_model_id: str | None = None,
    ) -> WorkerSession:
        if not provider_session_ref.strip():
            raise DdeError("VALIDATION_FAILED", "provider session ref is required")
        return await self._transition(
            tenant_id=tenant_id,
            project_id=project_id,
            worker_session_id=worker_session_id,
            lock_version=lock_version,
            target="ACTIVE",
            values={
                "provider_session_ref": provider_session_ref.strip(),
                "serving_model_id": serving_model_id,
                "last_error": None,
            },
        )

    async def transition(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        worker_session_id: UUID,
        lock_version: int,
        target: str,
        detail: str | None = None,
    ) -> WorkerSession:
        return await self._transition(
            tenant_id=tenant_id,
            project_id=project_id,
            worker_session_id=worker_session_id,
            lock_version=lock_version,
            target=target,
            values={"last_error": detail if target == "FAILED" else None},
        )

    async def fork(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        worker_session_id: UUID,
        session_config: dict[str, object] | None = None,
    ) -> WorkerSession:
        source = await self.get(
            tenant_id=tenant_id,
            project_id=project_id,
            worker_session_id=worker_session_id,
        )
        if source.state == "CLOSED":
            raise DdeError(
                "VERSION_CONFLICT", "closed provider session cannot be forked"
            )
        return await self.open(
            tenant_id=tenant_id,
            project_id=project_id,
            endpoint_id=source.endpoint_id,
            mission_id=source.mission_id,
            task_id=source.task_id,
            worker_profile_id=source.worker_profile_id,
            requested_model_id=source.requested_model_id,
            workspace_id=source.workspace_id,
            context_package_hash=source.context_package_hash,
            tool_policy_hash=source.tool_policy_hash,
            session_config=session_config or {},
            parent_session_id=source.worker_session_id,
            forked_from_session_id=source.worker_session_id,
        )

    async def _transition(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        worker_session_id: UUID,
        lock_version: int,
        target: str,
        values: dict[str, object],
    ) -> WorkerSession:
        current = await self.get(
            tenant_id=tenant_id,
            project_id=project_id,
            worker_session_id=worker_session_id,
        )
        if target not in _TRANSITIONS.get(current.state, frozenset()):
            raise DdeError(
                "VERSION_CONFLICT",
                "illegal provider session state transition",
                retryable=False,
                details={"from": current.state, "to": target},
            )
        now = datetime.now(UTC)
        return await self.repo.update_locked(
            table=worker_sessions,
            model=WorkerSession,
            id_column="worker_session_id",
            object_id=worker_session_id,
            tenant_id=tenant_id,
            project_id=project_id,
            lock_version=lock_version,
            values={
                **values,
                "state": target,
                "last_activity_at": now,
                "updated_at": now,
            },
        )
