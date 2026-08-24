"""DDE MCP server — Chapter 15.6 capability interoperability boundary."""

from __future__ import annotations

from interfaces.mcp.registry import TOOL_BY_NAME, TOOL_DECLARATIONS
from interfaces.mcp.server import McpStdioServer, build_bridge_from_env

__all__ = [
    "TOOL_BY_NAME",
    "TOOL_DECLARATIONS",
    "McpStdioServer",
    "build_bridge_from_env",
]
