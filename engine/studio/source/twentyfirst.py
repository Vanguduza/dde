"""Certified 21st.dev MCP transport for DDE-069 Source Intelligence.

The transport is deliberately narrower than a general MCP client. It can only
search/inspect/fetch catalog artifacts and it never invokes install/generate/
publish tools. The official 21st endpoint is registered with the AI
Conversation Fabric as DISCOVERED, but network execution requires an
independently CERTIFIED endpoint and a host-provided API_KEY_21ST. Credentials
are headers only and never enter DDE persistence or provider result metadata.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.agent_interop_endpoint import AgentInteropEndpoint
from engine.core.errors import DdeError
from engine.core.hashing import sha256_hex
from engine.fabric.interop import AgentInteropService
from engine.studio.source.adapters import (
    FetchedSource,
    SourceCandidate,
    SourceHealth,
    SourceQueryContext,
)

TWENTY_FIRST_MCP_URL = "https://21st.dev/api/mcp"
TWENTY_FIRST_HARNESS_ID = "21st"
MCP_PROTOCOL_VERSION = "2025-06-18"

ClientFactory = Callable[[], httpx.AsyncClient]


@dataclass(frozen=True)
class _McpTool:
    name: str
    input_schema: dict[str, object]


class TwentyFirstMcpTransport:
    """Read-only 21st MCP adapter admitted through Fabric certification."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        interop: AgentInteropService | None = None,
        api_key_env: str = "API_KEY_21ST",
        endpoint_url: str = TWENTY_FIRST_MCP_URL,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self._engine = engine
        self._interop = interop or AgentInteropService(engine)
        self._api_key_env = api_key_env
        self._endpoint_url = endpoint_url
        self._client_factory = client_factory or self._default_client

    def _default_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=8.0))

    async def health(self, context: SourceQueryContext) -> SourceHealth:
        endpoint = await self._certified_endpoint(context, register_if_missing=True)
        if endpoint is None:
            return SourceHealth(
                "NOT_CONFIGURED",
                ("search", "inspect", "fetch", "license", "health"),
                (
                    "21st MCP endpoint is discovered but not certified for "
                    "source retrieval"
                ),
            )
        api_key = os.environ.get(self._api_key_env, "").strip()
        if not api_key:
            return SourceHealth(
                "NOT_CONFIGURED",
                ("search", "inspect", "fetch", "license", "health"),
                (
                    f"{self._api_key_env} is not configured in the host "
                    "credential environment"
                ),
            )
        try:
            tools = await self._tools(api_key)
        except (httpx.HTTPError, DdeError, ValueError) as exc:
            return SourceHealth(
                "UNAVAILABLE",
                ("search", "inspect", "fetch", "license", "health"),
                f"21st MCP health failed: {type(exc).__name__}: {exc}",
            )
        has_search = self._choose_tool(tools, kind="search") is not None
        has_get = self._choose_tool(tools, kind="get") is not None
        if not has_search:
            return SourceHealth(
                "DEGRADED",
                ("health",),
                "certified 21st MCP endpoint does not currently expose a search tool",
            )
        capabilities = ["search", "health", "license"]
        if has_get:
            capabilities.extend(("inspect", "fetch"))
        return SourceHealth(
            "AVAILABLE" if has_get else "DEGRADED",
            tuple(capabilities),
            f"certified MCP endpoint; {len(tools)} tool(s) discovered",
        )

    async def search(
        self, context: SourceQueryContext, query: str
    ) -> tuple[SourceCandidate, ...]:
        api_key = await self._admit_call(context, capability="source_search")
        tools = await self._tools(api_key)
        tool = self._choose_tool(tools, kind="search")
        if tool is None:
            raise DdeError(
                "CAPABILITY_UNAVAILABLE",
                "certified 21st endpoint exposes no catalog search tool",
            )
        result = await self._call_tool(
            api_key,
            tool.name,
            self._arguments_for(tool, value=query, kind="search"),
        )
        return self._candidates_from_result(result, retrieval_state="INDEXED")

    async def inspect(
        self, context: SourceQueryContext, artifact_key: str
    ) -> SourceCandidate | None:
        api_key = await self._admit_call(context, capability="source_fetch")
        tools = await self._tools(api_key)
        tool = self._choose_tool(tools, kind="get")
        if tool is None:
            return None
        result = await self._call_tool(
            api_key,
            tool.name,
            self._arguments_for(tool, value=artifact_key, kind="get"),
        )
        rows = self._candidates_from_result(result, retrieval_state="INSPECTED")
        if not rows:
            return None
        return self._prefer(rows, artifact_key)

    async def fetch(
        self, context: SourceQueryContext, artifact_key: str
    ) -> FetchedSource | None:
        api_key = await self._admit_call(context, capability="source_fetch")
        tools = await self._tools(api_key)
        tool = self._choose_tool(tools, kind="get")
        if tool is None:
            return None
        result = await self._call_tool(
            api_key,
            tool.name,
            self._arguments_for(tool, value=artifact_key, kind="get"),
        )
        rows = self._candidates_from_result(result, retrieval_state="FETCHED")
        if not rows:
            return None
        candidate = self._prefer(rows, artifact_key)
        code = self._find_code(result, candidate.provider_artifact_key)
        content = code.encode("utf-8") if code is not None else None
        if content is not None:
            candidate = SourceCandidate(
                **{
                    **candidate.__dict__,
                    "content_hash": sha256_hex(content),
                    "retrieval_state": "FETCHED",
                }
            )
        return FetchedSource(candidate, content)

    async def _admit_call(self, context: SourceQueryContext, *, capability: str) -> str:
        endpoint = await self._certified_endpoint(context, register_if_missing=True)
        if endpoint is None:
            raise DdeError(
                "CAPABILITY_UNAVAILABLE",
                "21st MCP endpoint is not certified by DDE",
                details={"provider": "21st", "protocol": "MCP"},
            )
        certified = endpoint.certified_capabilities
        if not bool(certified.get("mcp")) or not bool(certified.get(capability)):
            raise DdeError(
                "CAPABILITY_UNAVAILABLE",
                f"21st endpoint is not certified for {capability}",
                details={"endpoint_id": str(endpoint.endpoint_id)},
            )
        api_key = os.environ.get(self._api_key_env, "").strip()
        if not api_key:
            raise DdeError(
                "CAPABILITY_UNAVAILABLE",
                f"{self._api_key_env} is not configured",
                details={"provider": "21st", "credential_state": "MISSING"},
            )
        return api_key

    async def _certified_endpoint(
        self, context: SourceQueryContext, *, register_if_missing: bool
    ) -> AgentInteropEndpoint | None:
        endpoints = await self._interop.list_endpoints(
            tenant_id=context.tenant_id, project_id=context.project_id
        )
        matching = [
            row
            for row in endpoints
            if row.harness_id == TWENTY_FIRST_HARNESS_ID
            and row.protocol == "MCP"
            and row.executable_or_uri == self._endpoint_url
        ]
        if not matching and register_if_missing:
            discovered = await self._interop.register_external(
                tenant_id=context.tenant_id,
                project_id=context.project_id,
                harness_id=TWENTY_FIRST_HARNESS_ID,
                protocol="MCP",
                executable_or_uri=self._endpoint_url,
                discovered_capabilities={
                    "mcp": True,
                    "source_search": True,
                    "source_fetch": True,
                },
            )
            matching = [discovered]
        return next(
            (row for row in matching if row.certification_state == "CERTIFIED"),
            None,
        )

    async def _tools(self, api_key: str) -> tuple[_McpTool, ...]:
        async with self._client_factory() as client:
            session_id = await self._initialize(client, api_key)
            payload = await self._rpc(
                client,
                api_key=api_key,
                method="tools/list",
                params={},
                request_id=2,
                session_id=session_id,
            )
        result = payload.get("result")
        if not isinstance(result, dict):
            raise DdeError("PROVIDER_ERROR", "21st MCP tools/list returned no result")
        raw_tools = result.get("tools")
        if not isinstance(raw_tools, list):
            raise DdeError("PROVIDER_ERROR", "21st MCP tools/list returned no tools")
        tools: list[_McpTool] = []
        for raw in raw_tools:
            if not isinstance(raw, dict) or not isinstance(raw.get("name"), str):
                continue
            schema = raw.get("inputSchema")
            tools.append(
                _McpTool(
                    name=str(raw["name"]),
                    input_schema=dict(schema) if isinstance(schema, dict) else {},
                )
            )
        return tuple(tools)

    async def _call_tool(
        self, api_key: str, tool_name: str, arguments: dict[str, object]
    ) -> dict[str, object]:
        async with self._client_factory() as client:
            session_id = await self._initialize(client, api_key)
            payload = await self._rpc(
                client,
                api_key=api_key,
                method="tools/call",
                params={"name": tool_name, "arguments": arguments},
                request_id=3,
                session_id=session_id,
            )
        if isinstance(payload.get("error"), dict):
            raise DdeError(
                "PROVIDER_ERROR",
                "21st MCP tool call failed",
                details={"tool": tool_name, "error": payload["error"]},
            )
        result = payload.get("result")
        if not isinstance(result, dict):
            raise DdeError("PROVIDER_ERROR", "21st MCP tool returned no result")
        return cast(dict[str, object], result)

    async def _initialize(self, client: httpx.AsyncClient, api_key: str) -> str | None:
        payload = await self._rpc(
            client,
            api_key=api_key,
            method="initialize",
            params={
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "dde-source-intelligence", "version": "1"},
            },
            request_id=1,
            session_id=None,
        )
        if not isinstance(payload.get("result"), dict):
            raise DdeError("PROVIDER_ERROR", "21st MCP initialization failed")
        return cast(str | None, payload.get("_dde_session_id"))

    async def _rpc(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str,
        method: str,
        params: dict[str, object],
        request_id: int,
        session_id: str | None,
    ) -> dict[str, object]:
        headers = {
            "x-api-key": api_key,
            "accept": "application/json, text/event-stream",
            "content-type": "application/json",
        }
        if session_id:
            headers["mcp-session-id"] = session_id
        response = await client.post(
            self._endpoint_url,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            },
        )
        response.raise_for_status()
        payload = self._decode_response(response)
        resolved_session = response.headers.get("mcp-session-id")
        if resolved_session:
            payload["_dde_session_id"] = resolved_session
        return payload

    @staticmethod
    def _decode_response(response: httpx.Response) -> dict[str, object]:
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" not in content_type:
            raw = response.json()
            if not isinstance(raw, dict):
                raise DdeError("PROVIDER_ERROR", "MCP response is not an object")
            return cast(dict[str, object], raw)
        events: list[dict[str, object]] = []
        for line in response.text.splitlines():
            if not line.startswith("data:"):
                continue
            body = line[5:].strip()
            if not body:
                continue
            try:
                raw = json.loads(body)
            except json.JSONDecodeError:
                continue
            if isinstance(raw, dict):
                events.append(cast(dict[str, object], raw))
        if not events:
            raise DdeError(
                "PROVIDER_ERROR", "MCP event stream contained no JSON result"
            )
        return events[-1]

    @staticmethod
    def _choose_tool(tools: tuple[_McpTool, ...], *, kind: str) -> _McpTool | None:
        lowered = {tool.name.lower(): tool for tool in tools}
        if kind == "search":
            for preferred in ("search", "search_components", "component_search"):
                if preferred in lowered:
                    return lowered[preferred]
            return next(
                (tool for tool in tools if "search" in tool.name.lower()),
                None,
            )
        for preferred in ("get_component", "get", "component_get"):
            if preferred in lowered:
                return lowered[preferred]
        return next(
            (
                tool
                for tool in tools
                if "component" in tool.name.lower()
                and any(
                    token in tool.name.lower() for token in ("get", "fetch", "read")
                )
            ),
            None,
        )

    @staticmethod
    def _arguments_for(tool: _McpTool, *, value: str, kind: str) -> dict[str, object]:
        properties = tool.input_schema.get("properties")
        names = set(properties) if isinstance(properties, dict) else set()
        preferred = (
            ("query", "search", "q", "prompt")
            if kind == "search"
            else ("component_id", "componentId", "id", "slug", "name", "component")
        )
        key = next((name for name in preferred if name in names), None)
        if key is None:
            key = preferred[0]
        return {key: value}

    @classmethod
    def _candidates_from_result(
        cls, result: dict[str, object], *, retrieval_state: str
    ) -> tuple[SourceCandidate, ...]:
        rows = cls._candidate_objects(result)
        normalized: list[SourceCandidate] = []
        seen: set[str] = set()
        for row in rows:
            key = cls._first_string(
                row,
                "component_id",
                "componentId",
                "id",
                "slug",
                "key",
                "url",
                "name",
                "title",
            )
            title = cls._first_string(row, "title", "name", "label", "slug")
            if not key or not title or key in seen:
                continue
            seen.add(key)
            code = cls._first_string(row, "code", "source", "content")
            dependencies = cls._string_list(
                row.get("dependencies") or row.get("dependency_manifest")
            )
            license_ids = cls._string_list(
                row.get("license_ids") or row.get("licenses") or row.get("license")
            )
            license_state = cls._license_state(license_ids)
            framework = cls._first_string(row, "framework", "runtime")
            if (
                framework is None
                and code
                and ('from "react"' in code or "from 'react'" in code)
            ):
                framework = "react"
            artifact_kind = str(
                row.get("kind") or row.get("type") or "COMPONENT"
            ).upper()
            if artifact_kind not in {
                "COMPONENT",
                "TEMPLATE",
                "THEME",
                "FOUNDATION",
                "DIRECTIVE",
                "REFERENCE",
            }:
                artifact_kind = "COMPONENT"
            normalized.append(
                SourceCandidate(
                    provider_artifact_key=key,
                    artifact_kind=artifact_kind,
                    title=title,
                    source_uri=cls._first_string(row, "url", "source_uri", "sourceUrl"),
                    version_ref=cls._first_string(row, "version", "version_ref"),
                    content_hash=sha256_hex(code.encode("utf-8")) if code else None,
                    framework=framework,
                    supported_archetypes=cls._string_list(
                        row.get("supported_archetypes") or row.get("tags")
                    ),
                    dependency_manifest=dependencies,
                    license_state=license_state,
                    license_ids=license_ids,
                    security_state="UNKNOWN",
                    accessibility_state="UNKNOWN",
                    compatibility_state="UNKNOWN",
                    retrieval_state=retrieval_state,
                    metadata={
                        "provider": "21st",
                        "provider_metadata": cls._safe_metadata(row),
                    },
                )
            )
        return tuple(normalized)

    @classmethod
    def _candidate_objects(
        cls, value: dict[str, object]
    ) -> tuple[dict[str, object], ...]:
        result: list[dict[str, object]] = []

        def visit(item: object) -> None:
            if isinstance(item, dict):
                if any(
                    key in item for key in ("id", "component_id", "componentId", "slug")
                ) and any(
                    key in item for key in ("name", "title", "code", "source", "url")
                ):
                    result.append(cast(dict[str, object], item))
                for child in item.values():
                    visit(child)
            elif isinstance(item, list):
                for child in item:
                    visit(child)
            elif isinstance(item, str):
                text = item.strip()
                if text.startswith(("{", "[")):
                    try:
                        visit(json.loads(text))
                    except json.JSONDecodeError:
                        pass

        visit(value.get("structuredContent"))
        visit(value.get("content"))
        visit(value)
        return tuple(result)

    @classmethod
    def _find_code(cls, result: dict[str, object], artifact_key: str) -> str | None:
        rows = cls._candidate_objects(result)
        preferred = next(
            (
                row
                for row in rows
                if artifact_key
                in {
                    cls._first_string(row, "component_id") or "",
                    cls._first_string(row, "componentId") or "",
                    cls._first_string(row, "id") or "",
                    cls._first_string(row, "slug") or "",
                    cls._first_string(row, "name") or "",
                }
            ),
            None,
        )
        rows_to_scan = (preferred,) if preferred is not None else rows
        for row in rows_to_scan:
            code = cls._first_string(row, "code", "source", "content")
            if code:
                return code
        return None

    @staticmethod
    def _prefer(rows: tuple[SourceCandidate, ...], key: str) -> SourceCandidate:
        return next(
            (row for row in rows if row.provider_artifact_key == key),
            rows[0],
        )

    @staticmethod
    def _first_string(row: dict[str, object], *keys: str) -> str | None:
        for key in keys:
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @classmethod
    def _string_list(cls, value: object) -> tuple[str, ...]:
        if isinstance(value, str):
            return (value,) if value.strip() else ()
        if isinstance(value, list):
            return tuple(str(item).strip() for item in value if str(item).strip())
        if isinstance(value, dict):
            return tuple(str(key) for key in value)
        return ()

    @staticmethod
    def _license_state(license_ids: tuple[str, ...]) -> str:
        if not license_ids:
            return "UNKNOWN"
        known_open = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"}
        return (
            "OPEN_REUSE"
            if all(item in known_open for item in license_ids)
            else "UNKNOWN"
        )

    @staticmethod
    def _safe_metadata(row: dict[str, object]) -> dict[str, object]:
        blocked = {"code", "source", "content", "token", "api_key", "apiKey", "secret"}
        return {key: value for key, value in row.items() if key not in blocked}
