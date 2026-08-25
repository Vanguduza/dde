"""MCP stdio + Gateway bridge proofs (Chapter 15.6, 19.1)."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.gateway.commands import GatewayCommandService
from engine.gateway.sessions.service import GatewaySessionService
from engine.missions.service import MissionService
from interfaces.mcp.gateway_bridge import McpGatewayBridge
from interfaces.mcp.server import McpStdioServer
from tests.support.db import new_engine, seed_tenant


async def _seed_grant(engine, *, tenant_id, principal_id, project_id) -> None:
    now = datetime.now(UTC)
    async with engine.connect() as connection:
        await connection.execute(
            text(
                "INSERT INTO principal_grants "
                "(grant_id, tenant_id, project_id, principal_id, scope_type, "
                "grant_scope, created_at, updated_at) "
                "VALUES (:grant_id, :tenant_id, :project_id, :principal_id, "
                "'PROJECT', 'PROJECT', :now, :now)"
            ),
            {
                "grant_id": uuid7(),
                "tenant_id": tenant_id,
                "project_id": project_id,
                "principal_id": principal_id,
                "now": now,
            },
        )
        await connection.commit()


@pytest.mark.asyncio
async def test_tools_list_does_not_require_session() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        bridge = McpGatewayBridge(engine, principal_id=fixture.principal_id)
        stdout = io.StringIO()
        server = McpStdioServer(bridge, stdout=stdout)
        await server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        await server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        lines = [json.loads(line) for line in stdout.getvalue().splitlines()]
        listed = lines[1]["result"]["tools"]
        names = {tool["name"] for tool in listed}
        assert "dde_get_mission" in names
        assert "dde_start_task" in names
        assert bridge.session is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_get_mission_goes_through_gateway() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        await _seed_grant(
            engine,
            tenant_id=fixture.tenant_id,
            principal_id=fixture.principal_id,
            project_id=fixture.project_id,
        )
        mission = await MissionService(engine, EventService(engine)).create_mission(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            slug=f"MISSION-MCP-{uuid7().hex[:8]}",
            title="MCP mission",
            intent="Prove MCP read path",
            success_definition="Readable via MCP",
            scope=["engine"],
            requirement_refs=[],
            autonomy_ceiling=1,
        )
        bridge = McpGatewayBridge(engine, principal_id=fixture.principal_id)
        result = await bridge.call_tool(
            name="dde_get_mission",
            arguments={"mission_id": str(mission.mission_id)},
        )
        assert result["mission"]["mission_id"] == str(mission.mission_id)
        assert bridge.session is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_ungatewayed_high_mutation_fails_closed() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        bridge = McpGatewayBridge(engine, principal_id=fixture.principal_id)
        with pytest.raises(DdeError) as exc_info:
            await bridge.call_tool(
                name="dde_start_task",
                arguments={
                    "task_id": str(uuid7()),
                    "execution_plan_id": str(uuid7()),
                    "idempotency_key": "mcp-start-1",
                },
            )
        assert exc_info.value.error_code == "POLICY_DENIED"
        assert bridge.session is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_mutation_without_idempotency_key_is_forbidden() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        bridge = McpGatewayBridge(engine, principal_id=fixture.principal_id)
        with pytest.raises(DdeError) as exc_info:
            await bridge.call_tool(
                name="dde_start_task",
                arguments={
                    "task_id": str(uuid7()),
                    "execution_plan_id": str(uuid7()),
                },
            )
        assert exc_info.value.error_code == "FORBIDDEN"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_gateway_command_accept_path_is_reachable() -> None:
    """Future gateway-backed mutations share accept_gateway_command."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        await _seed_grant(
            engine,
            tenant_id=fixture.tenant_id,
            principal_id=fixture.principal_id,
            project_id=fixture.project_id,
        )
        bridge = McpGatewayBridge(
            engine,
            principal_id=fixture.principal_id,
            sessions=GatewaySessionService(engine),
            commands=GatewayCommandService(engine),
        )
        acceptance = await bridge.accept_gateway_command(
            command_type="mission.create",
            target_type="project",
            target_id=fixture.project_id,
            parameters={
                "slug": f"MISSION-MCP-CMD-{uuid7().hex[:8]}",
                "title": "MCP command",
                "intent": "Gateway accept path",
                "success_definition": "Accepted",
                "scope": ["engine"],
                "requirement_refs": [],
                "autonomy_ceiling": 1,
            },
            idempotency_key=f"mcp-create-{uuid7().hex[:8]}",
        )
        assert acceptance["status"] == "accepted"
        assert acceptance["command_id"]
    finally:
        await engine.dispose()
