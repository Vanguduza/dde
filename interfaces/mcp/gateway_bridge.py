"""MCP → Gateway bridge (Chapter 15.6 security rule).

Tool discovery never authorizes. Every mutating or reading call that this
module accepts is dispatched through `GatewayCommandService` /
`GatewaySessionService` — the same admission path as `/v1`. No core tables
are read or written here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.client_session import ClientSession
from engine.contracts.command import Command
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.gateway.commands import GatewayCommandService
from engine.gateway.scopes import BASELINE_SCOPES
from engine.gateway.sessions.service import GatewaySessionService
from interfaces.mcp.registry import TOOL_BY_NAME, McpToolDeclaration


class McpGatewayBridge:
    """Session-bound dispatcher. Constructed once per MCP server process."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        principal_id: UUID,
        client_type: str = "human",
        sessions: GatewaySessionService | None = None,
        commands: GatewayCommandService | None = None,
    ) -> None:
        self._engine = engine
        self._principal_id = principal_id
        self._client_type = client_type
        self._sessions = sessions or GatewaySessionService(engine)
        self._commands = commands or GatewayCommandService(
            engine, sessions=self._sessions
        )
        self._session: ClientSession | None = None

    @property
    def session(self) -> ClientSession | None:
        return self._session

    async def ensure_session(self) -> ClientSession:
        if self._session is not None and self._session.status == "ACTIVE":
            return self._session
        baseline = BASELINE_SCOPES.get(self._client_type)
        if baseline is None:
            raise DdeError(
                "FORBIDDEN",
                "Unsupported MCP client_type",
                details={"client_type": self._client_type},
            )
        self._session = await self._sessions.open_session(
            principal_id=self._principal_id,
            client_type=self._client_type,
            scopes=sorted(baseline),
            subscriptions=["mission"],
        )
        return self._session

    async def close(self) -> None:
        if self._session is None:
            return
        await self._sessions.close_session(session_id=self._session.session_id)
        self._session = None

    async def call_tool(
        self, *, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        declaration = TOOL_BY_NAME.get(name)
        if declaration is None:
            raise DdeError(
                "FORBIDDEN",
                "Unknown MCP tool",
                details={"tool": name},
            )
        if declaration.idempotency_required and not isinstance(
            arguments.get("idempotency_key"), str
        ):
            raise DdeError(
                "FORBIDDEN",
                "idempotency_key is required for this MCP tool",
                details={"tool": name},
            )
        if not declaration.gateway_backed:
            raise DdeError(
                "POLICY_DENIED",
                "MCP tool is declared but not yet gateway-backed; "
                "refusing rather than bypassing Mission Kernel",
                details={
                    "tool": name,
                    "mutation": declaration.mutation,
                    "gateway_backed": False,
                },
            )
        session = await self.ensure_session()
        return await self._dispatch_gateway_backed(
            declaration=declaration, session=session, arguments=arguments
        )

    async def _dispatch_gateway_backed(
        self,
        *,
        declaration: McpToolDeclaration,
        session: ClientSession,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if declaration.name == "dde_get_mission":
            mission_id = _require_uuid(arguments, "mission_id")
            mission = await self._commands.read_mission(
                session_id=session.session_id,
                principal_id=self._principal_id,
                mission_id=mission_id,
            )
            return {"mission": mission.model_dump(mode="json")}

        if declaration.name == "dde_get_task":
            task_id = _require_uuid(arguments, "task_id")
            task = await self._commands.read_task(
                session_id=session.session_id,
                principal_id=self._principal_id,
                task_id=task_id,
            )
            return {"task": task.model_dump(mode="json")}

        if declaration.name == "dde_get_graph":
            graph_id = _require_uuid(arguments, "graph_id")
            graph = await self._commands.read_task_graph(
                session_id=session.session_id,
                principal_id=self._principal_id,
                graph_id=graph_id,
            )
            return {"graph": graph.model_dump(mode="json")}

        raise DdeError(
            "POLICY_DENIED",
            "Gateway-backed MCP tool has no dispatcher",
            details={"tool": declaration.name},
        )

    async def accept_gateway_command(
        self,
        *,
        command_type: str,
        target_type: str,
        target_id: UUID,
        parameters: dict[str, object],
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Shared mutation path for future gateway-backed MCP tools."""
        session = await self.ensure_session()
        command = Command(
            command_id=uuid7(),
            idempotency_key=idempotency_key,
            principal_id=self._principal_id,
            client_session_id=session.session_id,
            target_type=target_type,
            target_id=target_id,
            command_type=command_type,
            parameters=parameters,
            requested_at=datetime.now(UTC),
            protocol_version="1",
        )
        acceptance = await self._commands.accept(command=command)
        return {
            "command_id": str(acceptance.command_id),
            "status": acceptance.status,
            "target_type": acceptance.target_type,
            "target_id": str(acceptance.target_id),
            "payload": acceptance.payload,
        }


def _require_uuid(arguments: dict[str, Any], name: str) -> UUID:
    value = arguments.get(name)
    if value is None:
        raise DdeError(
            "FORBIDDEN",
            f"Missing parameter '{name}'",
            details={"parameter": name},
        )
    try:
        return UUID(str(value))
    except ValueError as exc:
        raise DdeError(
            "FORBIDDEN",
            f"Invalid UUID for '{name}'",
            details={"parameter": name, "value": str(value)},
        ) from exc
