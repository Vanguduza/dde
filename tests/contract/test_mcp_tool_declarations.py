"""Chapter 19.1 contract suite for Chapter 15.6 MCP tool declarations.

Pins: every Chapter 15.6 tool name is registered; every declaration carries
the required metadata fields; discovery metadata never implies
authorization (gateway_backed is explicit); mutation tools require
idempotency.
"""

from __future__ import annotations

from interfaces.mcp.registry import (
    CHAPTER_15_6_TOOL_NAMES,
    TOOL_BY_NAME,
    TOOL_DECLARATIONS,
    McpToolDeclaration,
)

_REQUIRED_METADATA = (
    "name",
    "version",
    "description",
    "tool_class",
    "input_schema",
    "output_schema",
    "required_scopes",
    "mutation",
    "idempotency_required",
    "target_resource",
    "audit_event_type",
    "error_codes",
    "execution",
    "gateway_backed",
)


def test_every_chapter_15_6_tool_is_declared() -> None:
    declared = {tool.name for tool in TOOL_DECLARATIONS}
    assert declared == CHAPTER_15_6_TOOL_NAMES


def test_tool_names_are_unique() -> None:
    names = [tool.name for tool in TOOL_DECLARATIONS]
    assert len(names) == len(set(names))


def test_every_declaration_carries_required_metadata() -> None:
    for tool in TOOL_DECLARATIONS:
        for field in _REQUIRED_METADATA:
            assert getattr(tool, field) is not None, (tool.name, field)
        assert tool.input_schema.get("$schema", "").endswith("2020-12/schema")
        assert tool.output_schema.get("$schema", "").endswith("2020-12/schema")
        assert tool.version
        assert tool.required_scopes
        assert tool.error_codes
        assert tool.audit_event_type
        assert tool.mutation in {"none", "controlled", "high"}
        assert tool.execution in {"sync", "async"}


def test_mutation_tools_require_idempotency() -> None:
    for tool in TOOL_DECLARATIONS:
        if tool.mutation == "none":
            assert tool.idempotency_required is False
        else:
            assert tool.idempotency_required is True, tool.name
            assert "idempotency_key" in tool.input_schema["required"]


def test_discovery_lists_tools_that_are_not_yet_authorized() -> None:
    """Chapter 15.6 security rule: schema disclosure ≠ authorization.
    Non-gateway-backed tools remain discoverable and fail closed on call."""
    undeclared_surface = [tool for tool in TOOL_DECLARATIONS if not tool.gateway_backed]
    assert undeclared_surface, "expected deferred tools to remain declared"
    assert TOOL_BY_NAME["dde_get_mission"].gateway_backed is True
    assert TOOL_BY_NAME["dde_get_task"].gateway_backed is True
    assert TOOL_BY_NAME["dde_get_graph"].gateway_backed is True
    assert TOOL_BY_NAME["dde_start_task"].gateway_backed is False
    assert TOOL_BY_NAME["dde_start_task"].mutation == "high"


def test_lookup_returns_declaration() -> None:
    tool = TOOL_BY_NAME["dde_get_mission"]
    assert isinstance(tool, McpToolDeclaration)
    assert tool.tool_class == "Read"
