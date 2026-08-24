"""DDE MCP server entry (Chapter 15.6).

Dependency admission (Chapter 9.6 / AGENTS.md): no new top-level package.
The MCP JSON-RPC framing used here is stdlib-only; Gateway admission is
why the stdlib alone is insufficient for *authorization*.
"""

from __future__ import annotations

import asyncio
import sys

from interfaces.mcp.server import McpStdioServer, build_bridge_from_env


def main() -> None:
    async def _run() -> None:
        bridge = build_bridge_from_env()
        server = McpStdioServer(bridge)
        try:
            await server.serve_forever()
        finally:
            await bridge.close()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
