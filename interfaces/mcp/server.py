"""Minimal MCP JSON-RPC 2.0 stdio server (Chapter 15.6).

No third-party MCP SDK: the protocol surface used here is initialize,
tools/list, tools/call, and ping — implementable with the stdlib. The
stdlib cannot speak the MCP *semantics* for DDE (Gateway admission,
scopes, idempotency); those live in `gateway_bridge`.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from typing import Any, TextIO
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.core.errors import DdeError
from engine.gateway.settings import get_settings
from engine.truth.db import build_engine
from interfaces.mcp.gateway_bridge import McpGatewayBridge
from interfaces.mcp.registry import TOOL_DECLARATIONS


class McpStdioServer:
    """One MCP session over stdin/stdout newline-delimited JSON-RPC."""

    def __init__(
        self,
        bridge: McpGatewayBridge,
        *,
        stdin: TextIO | None = None,
        stdout: TextIO | None = None,
    ) -> None:
        self._bridge = bridge
        self._stdin = stdin or sys.stdin
        self._stdout = stdout or sys.stdout
        self._initialized = False

    def _write(self, message: dict[str, Any]) -> None:
        self._stdout.write(json.dumps(message, default=str) + "\n")
        self._stdout.flush()

    def _result(self, request_id: object, result: object) -> None:
        self._write({"jsonrpc": "2.0", "id": request_id, "result": result})

    def _error(
        self, request_id: object, *, code: int, message: str, data: object = None
    ) -> None:
        error: dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        self._write({"jsonrpc": "2.0", "id": request_id, "error": error})

    async def handle(self, request: Mapping[str, Any]) -> None:
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}
        if not isinstance(params, dict):
            params = {}

        try:
            if method == "initialize":
                self._initialized = True
                self._result(
                    request_id,
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "dde-mcp", "version": "0.1.0"},
                        # Discovery never authorizes: session opens on first
                        # tools/call, not on initialize.
                        "instructions": (
                            "DDE MCP tools declare schemas freely; every "
                            "tools/call is authorized by Gateway scopes and, "
                            "where required, CapabilityLease. Listing tools "
                            "grants nothing."
                        ),
                    },
                )
                return
            if method == "notifications/initialized":
                return
            if method == "ping":
                self._result(request_id, {})
                return
            if method == "tools/list":
                # Chapter 15.6: tool discovery / schema disclosure never
                # constitutes DDE authorization.
                tools = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.input_schema,
                        "_dde": {
                            "version": tool.version,
                            "tool_class": tool.tool_class,
                            "mutation": tool.mutation,
                            "idempotency_required": tool.idempotency_required,
                            "required_scopes": list(tool.required_scopes),
                            "target_resource": tool.target_resource,
                            "audit_event_type": tool.audit_event_type,
                            "error_codes": list(tool.error_codes),
                            "execution": tool.execution,
                            "gateway_backed": tool.gateway_backed,
                            "outputSchema": tool.output_schema,
                        },
                    }
                    for tool in TOOL_DECLARATIONS
                ]
                self._result(request_id, {"tools": tools})
                return
            if method == "tools/call":
                if not self._initialized:
                    self._error(
                        request_id,
                        code=-32002,
                        message="MCP server not initialized",
                    )
                    return
                name = str(params.get("name") or "")
                arguments = params.get("arguments") or {}
                if not isinstance(arguments, dict):
                    arguments = {}
                result = await self._bridge.call_tool(name=name, arguments=arguments)
                self._result(
                    request_id,
                    {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result, default=str),
                            }
                        ],
                        "structuredContent": result,
                        "isError": False,
                    },
                )
                return
            if request_id is not None:
                self._error(
                    request_id,
                    code=-32601,
                    message=f"Method not found: {method}",
                )
        except DdeError as exc:
            if request_id is None:
                return
            self._result(
                request_id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                exc.to_contract().model_dump(mode="json"),
                                default=str,
                            ),
                        }
                    ],
                    "structuredContent": exc.to_contract().model_dump(mode="json"),
                    "isError": True,
                },
            )

    async def serve_forever(self) -> None:
        for line in self._stdin:
            text = line.strip()
            if not text:
                continue
            try:
                request = json.loads(text)
            except json.JSONDecodeError:
                self._error(None, code=-32700, message="Parse error")
                continue
            if not isinstance(request, dict):
                continue
            await self.handle(request)


def build_bridge_from_env(engine: AsyncEngine | None = None) -> McpGatewayBridge:
    settings = get_settings()
    principal_raw = getattr(settings, "mcp_principal_id", None) or _env_uuid(
        "DDE_MCP_PRINCIPAL_ID"
    )
    if principal_raw is None:
        raise DdeError(
            "INVALID_CREDENTIALS",
            "DDE_MCP_PRINCIPAL_ID is required to run the MCP server",
        )
    return McpGatewayBridge(
        engine or build_engine(settings.database_url),
        principal_id=principal_raw,
        client_type=_env_str("DDE_MCP_CLIENT_TYPE", "human"),
    )


def _env_uuid(name: str) -> UUID | None:
    import os

    raw = os.environ.get(name)
    if not raw:
        return None
    return UUID(raw)


def _env_str(name: str, default: str) -> str:
    import os

    return os.environ.get(name, default)
