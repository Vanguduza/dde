"""Gateway command acceptance (Chapter 15.1, 15.2).

The gateway is a thin transport boundary: it authenticates and authorizes a
command before it reaches Core, enforces the idempotency key, and separates
command acceptance (202) from eventual completion. It never owns Project
Truth or mission state — the dispatched domain service is the authoritative
mutation (Chapter 15.1).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.client_session import ClientSession
from engine.contracts.command import Command
from engine.contracts.mission import Mission
from engine.contracts.mission_control import MissionControl
from engine.core.errors import DdeError
from engine.events.idempotency import CommandLedger
from engine.events.service import EventService
from engine.gateway.scopes import (
    MISSION_CONTROL_TARGETS,
    required_scope,
    required_target_type,
)
from engine.gateway.sessions.service import GatewaySessionService
from engine.missions.repository import MissionsRepository
from engine.missions.service import MissionService
from engine.projections.service import MissionControlService


@dataclass(frozen=True)
class CommandAcceptance:
    """202-accepted result (Chapter 15.1: acceptance is not completion)."""

    command_id: UUID
    status: str
    target_type: str
    target_id: UUID
    payload: dict[str, object]


def _hash_command(command: Command) -> str:
    """Fingerprint the logical command identity, excluding per-attempt fields
    (`command_id`, `idempotency_key`, `requested_at`, principal/session) so a
    true retry hashes identically while key reuse with a different logical
    command is refused (Chapter 12.5)."""
    canonical = json.dumps(
        {
            "command_type": command.command_type,
            "target_type": command.target_type,
            "target_id": str(command.target_id),
            "parameters": command.parameters,
            "protocol_version": command.protocol_version,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _param_str(parameters: dict[str, object], name: str) -> str:
    value = parameters.get(name)
    if not isinstance(value, str):
        raise DdeError(
            "FORBIDDEN",
            f"Missing or invalid parameter '{name}'",
            details={"parameter": name},
        )
    return value


def _param_list(parameters: dict[str, object], name: str) -> list[str]:
    value = parameters.get(name)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise DdeError(
            "FORBIDDEN",
            f"Missing or invalid parameter '{name}'",
            details={"parameter": name},
        )
    return value


def _param_int(parameters: dict[str, object], name: str) -> int:
    value = parameters.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise DdeError(
            "FORBIDDEN",
            f"Missing or invalid parameter '{name}'",
            details={"parameter": name},
        )
    return value


class CommandDispatcher:
    """Dispatches an authorized command onto its owning domain service."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def _missions(self) -> MissionService:
        return MissionService(self._engine, EventService(self._engine))

    async def load_mission(self, mission_id: UUID) -> Mission:
        async with self._engine.connect() as connection:
            mission = await MissionsRepository().get_mission(connection, mission_id)
        if mission is None:
            raise DdeError(
                "POLICY_DENIED",
                "Unknown mission",
                details={"mission_id": str(mission_id)},
            )
        return mission

    async def dispatch(
        self,
        *,
        command: Command,
        tenant_id: UUID,
        project_id: UUID,
    ) -> CommandAcceptance:
        command_type = command.command_type
        if command_type == "mission.create":
            return await self._create_mission(command, tenant_id, project_id)
        if command_type in MISSION_CONTROL_TARGETS:
            return await self._control_mission(
                command, tenant_id, project_id, command_type
            )
        raise DdeError(
            "FORBIDDEN",
            "Unsupported command_type",
            details={"command_type": command_type},
        )

    async def _create_mission(
        self, command: Command, tenant_id: UUID, project_id: UUID
    ) -> CommandAcceptance:
        params = command.parameters
        mission = await self._missions().create_mission(
            tenant_id=tenant_id,
            project_id=project_id,
            slug=_param_str(params, "slug"),
            title=_param_str(params, "title"),
            intent=_param_str(params, "intent"),
            success_definition=_param_str(params, "success_definition"),
            scope=_param_list(params, "scope"),
            requirement_refs=_param_list(params, "requirement_refs"),
            autonomy_ceiling=_param_int(params, "autonomy_ceiling"),
        )
        return CommandAcceptance(
            command_id=command.command_id,
            status="accepted",
            target_type="mission",
            target_id=mission.mission_id,
            payload={"mission_id": str(mission.mission_id), "status": mission.status},
        )

    async def _control_mission(
        self,
        command: Command,
        tenant_id: UUID,
        project_id: UUID,
        command_type: str,
    ) -> CommandAcceptance:
        target_status = MISSION_CONTROL_TARGETS[command_type]
        params = command.parameters
        lock_version = _param_int(params, "lock_version")
        mission = await self._missions().transition_mission(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=command.target_id,
            target_status=target_status,
            lock_version=lock_version,
        )
        return CommandAcceptance(
            command_id=command.command_id,
            status="accepted",
            target_type="mission",
            target_id=mission.mission_id,
            payload={"mission_id": str(mission.mission_id), "status": mission.status},
        )


class GatewayCommandService:
    """Composes session authorization, project authorization, the idempotency
    ledger and domain dispatch into one command-acceptance path (Chapter
    15.1, 15.2, 15.3)."""

    def __init__(
        self,
        engine: AsyncEngine,
        sessions: GatewaySessionService | None = None,
        dispatcher: CommandDispatcher | None = None,
        ledger: CommandLedger | None = None,
        projections: MissionControlService | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = sessions or GatewaySessionService(engine)
        self._dispatcher = dispatcher or CommandDispatcher(engine)
        self._ledger = ledger or CommandLedger(engine)
        self._projections = projections or MissionControlService(engine)

    async def accept(self, *, command: Command) -> CommandAcceptance:
        if command.client_session_id is None:
            raise DdeError(
                "SESSION_EXPIRED",
                "client_session_id is required to authorize a command",
            )
        scope = required_scope(command.command_type)
        session = await self._sessions.authorize_scope(
            session_id=command.client_session_id,
            principal_id=command.principal_id,
            required_scope=scope,
        )
        project_id = await self._resolve_project(command, session)
        request_hash = _hash_command(command)
        record, is_new = await self._ledger.begin(
            tenant_id=session.tenant_id,
            project_id=project_id,
            idempotency_key=command.idempotency_key,
            request_hash=request_hash,
        )
        if not is_new:
            return self._replay(
                command, record.command_id, record.status, record.result
            )
        try:
            acceptance = await self._dispatcher.dispatch(
                command=command,
                tenant_id=session.tenant_id,
                project_id=project_id,
            )
        except DdeError:
            await self._ledger.fail(
                tenant_id=session.tenant_id,
                project_id=project_id,
                command_id=record.command_id,
            )
            raise
        await self._ledger.complete(
            tenant_id=session.tenant_id,
            project_id=project_id,
            command_id=record.command_id,
            result={
                "target_type": acceptance.target_type,
                "target_id": str(acceptance.target_id),
                "payload": acceptance.payload,
            },
        )
        return acceptance

    async def read_mission(
        self, *, session_id: UUID, principal_id: UUID, mission_id: UUID
    ) -> Mission:
        session = await self._sessions.authorize_scope(
            session_id=session_id,
            principal_id=principal_id,
            required_scope="mission.read",
        )
        mission = await self._dispatcher.load_mission(mission_id)
        if mission.tenant_id != session.tenant_id:
            raise DdeError(
                "TENANT_SCOPE_VIOLATION",
                "Mission belongs to another tenant",
                details={"mission_id": str(mission_id)},
            )
        await self._sessions.authorize_project(session, mission.project_id)
        return mission

    async def read_mission_control(
        self, *, session_id: UUID, principal_id: UUID, mission_id: UUID
    ) -> MissionControl:
        """Operational projection (Chapter 15.4 `GET /v1/mission-control/{id}`).

        Authorizes `mission.read` on the session, verifies the mission belongs
        to the session's tenant, then authorizes the principal for the mission's
        project before building the read model — the same fail-closed order as
        `read_mission`.
        """
        session = await self._sessions.authorize_scope(
            session_id=session_id,
            principal_id=principal_id,
            required_scope="mission.read",
        )
        mission = await self._dispatcher.load_mission(mission_id)
        if mission.tenant_id != session.tenant_id:
            raise DdeError(
                "TENANT_SCOPE_VIOLATION",
                "Mission belongs to another tenant",
                details={"mission_id": str(mission_id)},
            )
        await self._sessions.authorize_project(session, mission.project_id)
        return await self._projections.project(
            tenant_id=session.tenant_id,
            project_id=mission.project_id,
            mission_id=mission_id,
        )

    async def _resolve_project(self, command: Command, session: ClientSession) -> UUID:
        expected = required_target_type(command.command_type)
        if command.target_type != expected:
            raise DdeError(
                "FORBIDDEN",
                f"{command.command_type} requires target_type '{expected}'",
                details={"target_type": command.target_type},
            )
        if command.target_type == "project":
            project_id = command.target_id
        else:
            mission = await self._dispatcher.load_mission(command.target_id)
            if mission.tenant_id != session.tenant_id:
                raise DdeError(
                    "TENANT_SCOPE_VIOLATION",
                    "Mission belongs to another tenant",
                    details={"mission_id": str(command.target_id)},
                )
            project_id = mission.project_id
        await self._sessions.authorize_project(session, project_id)
        return project_id

    def _replay(
        self,
        command: Command,
        command_id: UUID,
        status: str,
        result: dict[str, object] | None,
    ) -> CommandAcceptance:
        if status == "completed" and result is not None:
            return CommandAcceptance(
                command_id=command_id,
                status="completed",
                target_type=str(result["target_type"]),
                target_id=UUID(str(result["target_id"])),
                payload=result["payload"]
                if isinstance(result["payload"], dict)
                else {},
            )
        return CommandAcceptance(
            command_id=command_id,
            status=status,
            target_type=command.target_type,
            target_id=command.target_id,
            payload={},
        )
