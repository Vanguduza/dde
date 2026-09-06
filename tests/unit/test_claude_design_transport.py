"""DDE-069 — the Claude Design transport's boundary, without a live provider.

Every assertion here runs against a fake host process. That is deliberate:
a transport whose governance properties can only be checked by spending a
real model call has no governance properties in CI. The live proof is a
separate, explicitly gated run (`tests/live/test_claude_design_live_e2e.py`).

What is under test is the part that decides whether `/design` is safe:
which argv the host is actually launched with, that a stream disagreeing
with those flags is refused rather than trusted, that a manifest claiming
deliverables nobody wrote is refused, and that each failure keeps its own
typed state instead of collapsing into "unavailable".
"""

from __future__ import annotations

import json

import pytest

from engine.core.errors import DdeError
from engine.studio.design.claude_transport import (
    ALLOWED_BUILTIN_TOOLS,
    ENV_ENABLED,
    HOST_BUILTIN_TOOLS,
    ClaudeDesignMcpTransport,
    ClaudeDesignTransportConfig,
    build_prompt,
    generate_argv,
    parse_stream,
    settings_document,
    transport_from_environment,
)
from engine.studio.design.context import DesignEditContext, DesignSystemSnapshot
from engine.studio.design.manifest import MANIFEST_PATH, MANIFEST_VERSION
from engine.studio.design.providers import (
    ClaudeDesignProvider,
    DesignRequest,
    ProviderState,
    default_registry,
)

PREFIX = "mcp__claude-design__"
PROJECT = "proj-1234"


def _context() -> DesignEditContext:
    return DesignEditContext(
        scope_keys=("screens/checkout",),
        design_system=DesignSystemSnapshot(
            tokens={"spacing": ["space2", "space6"]}, version="1"
        ),
        nodes=(
            {
                "pxg_key": "screens/checkout",
                "node_kind": "screen",
                "attributes": {},
                "materialization": {"token_edit": False},
            },
            {
                "pxg_key": "screens/checkout#hero",
                "node_kind": "region",
                "attributes": {},
                "materialization": {"token_edit": True},
            },
        ),
        obligations=(),
        pxg_revision=4,
        contract_version=2,
    )


def _request(direction_count: int = 2) -> DesignRequest:
    return DesignRequest(
        context=_context(),
        direction_count=direction_count,
        instruction="/design two hero alternatives for screens/checkout",
    )


def _manifest(request: DesignRequest, *, labels: tuple[str, ...] = ("A", "B")) -> dict:
    context = request.context
    return {
        "manifest_version": MANIFEST_VERSION,
        "provider_project_id": PROJECT,
        "provider_project_url": "https://claude.ai/design/proj-1234",
        "design_system_hash": context.design_system.content_hash,
        "context_hash": context.content_hash,
        "directions": [
            {
                "label": label,
                "summary": f"Direction {label}",
                "rationale": "denser hero",
                "preview_path": f"direction-{label.lower()}.html",
                "nodes": [
                    {
                        "pxg_key": "screens/checkout#hero",
                        "intent": "tighten the hero",
                        "tokens": {"spacing": "space6"},
                    }
                ],
            }
            for label in labels
        ],
    }


def _stream(
    manifest: dict | None,
    *,
    tools: tuple[str, ...] = (
        *ALLOWED_BUILTIN_TOOLS,
        f"{PREFIX}create_project",
        f"{PREFIX}write_files",
    ),
    mcp_servers: tuple[tuple[str, str], ...] = (("claude-design", "connected"),),
    calls: tuple[tuple[str, dict, bool], ...] | None = None,
    subtype: str = "success",
    is_error: bool = False,
    permission_denials: tuple[str, ...] = (),
) -> str:
    """Render a plausible `stream-json` transcript."""
    if calls is None and manifest is not None:
        paths = [MANIFEST_PATH] + [
            item["preview_path"] for item in manifest["directions"]
        ]
        calls = (
            (
                f"{PREFIX}write_files",
                {
                    "project_id": manifest["provider_project_id"],
                    "files": [{"path": path, "data": "<html/>"} for path in paths],
                },
                False,
            ),
        )
    lines: list[str] = [
        json.dumps(
            {
                "type": "system",
                "subtype": "init",
                "session_id": "session-1",
                "claude_code_version": "2.1.259",
                "model": "claude-sonnet-5",
                "permissionMode": "dontAsk",
                "tools": list(tools),
                "mcp_servers": [
                    {"name": name, "status": state} for name, state in mcp_servers
                ],
            }
        )
    ]
    for index, (name, payload, failed) in enumerate(calls or ()):
        use_id = f"toolu_{index}"
        lines.append(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": use_id,
                                "name": name,
                                "input": payload,
                            }
                        ]
                    },
                }
            )
        )
        lines.append(
            json.dumps(
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": use_id,
                                "is_error": failed,
                            }
                        ]
                    },
                }
            )
        )
    lines.append(
        json.dumps(
            {
                "type": "result",
                "subtype": subtype,
                "is_error": is_error,
                "result": "done",
                "structured_output": manifest,
                "permission_denials": [
                    {"tool_name": name} for name in permission_denials
                ],
                "total_cost_usd": 0.41,
            }
        )
    )
    return "\n".join(lines) + "\n"


_AUTH_OK = json.dumps(
    {
        "loggedIn": True,
        "authMethod": "claude.ai",
        "subscriptionType": "max",
        "orgId": "org-1",
        "email": "someone@example.com",
    }
)
_HEALTH_OK = (
    "Checking MCP server health…\n\n"
    "claude-design: https://api.anthropic.com/v1/design/mcp (HTTP) - ✔ Connected\n"
)


class FakeHost:
    """Stands in for the `claude` executable. Records every argv."""

    def __init__(
        self,
        *,
        auth: tuple[int, str] = (0, _AUTH_OK),
        health: tuple[int, str] = (0, _HEALTH_OK),
        generate: tuple[int, str] = (0, ""),
    ) -> None:
        self.auth = auth
        self.health = health
        self.generate = generate
        self.invocations: list[tuple[str, ...]] = []

    async def __call__(
        self, argv: tuple[str, ...], *, cwd: str | None, timeout_seconds: float
    ) -> tuple[int, str, str]:
        self.invocations.append(argv)
        if "auth" in argv:
            return self.auth[0], self.auth[1], ""
        if "mcp" in argv and "list" in argv:
            return self.health[0], self.health[1], ""
        return self.generate[0], self.generate[1], ""


def _transport(host: FakeHost, **overrides: object) -> ClaudeDesignMcpTransport:
    config = ClaudeDesignTransportConfig(binary="claude", **overrides)  # type: ignore[arg-type]
    # A private cache per transport: the production one is process-scoped,
    # and a shared cache would let one test's health answer decide another's.
    return ClaudeDesignMcpTransport(config, runner=host, cache={})


@pytest.fixture
def on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "engine.studio.design.claude_transport.shutil.which",
        lambda name: f"/usr/local/bin/{name}",
    )


# --- activation --------------------------------------------------------


def test_the_transport_is_absent_unless_the_operator_enables_it() -> None:
    """Discovering the CLI is not authorisation to use it."""
    assert transport_from_environment({}) is None
    assert transport_from_environment({ENV_ENABLED: "0"}) is None
    assert transport_from_environment({ENV_ENABLED: "true"}) is not None


def test_an_unconfigured_build_still_reports_the_uncertified_reason() -> None:
    registry = default_registry(env={})
    provider = registry.known()[0]
    assert isinstance(provider, ClaudeDesignProvider)


@pytest.mark.asyncio
async def test_an_unconfigured_build_refuses_with_no_fallback() -> None:
    with pytest.raises(DdeError) as excinfo:
        await default_registry(env={}).resolve("claude-design")
    assert excinfo.value.error_code == "CAPABILITY_UNAVAILABLE"
    assert excinfo.value.details["state"] == "NOT_CERTIFIED"


def test_configuration_never_hardcodes_a_host_path() -> None:
    config = ClaudeDesignTransportConfig.from_environment(
        {ENV_ENABLED: "1", "DDE_CLAUDE_DESIGN_BINARY": "/opt/tools/claude"}
    )
    assert config is not None
    assert config.binary == "/opt/tools/claude"


# --- the invocation ----------------------------------------------------


def test_the_host_is_launched_with_only_the_design_mcp_and_no_file_tools() -> None:
    config = ClaudeDesignTransportConfig(binary="claude")
    argv = generate_argv(
        config, settings_path="/tmp/s.json", mcp_config_path="/tmp/m.json", prompt="hi"
    )
    assert argv[-1] == "hi", "the prompt must never be swallowed by a variadic flag"
    for flag in (
        "--print",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--disable-slash-commands",
    ):
        assert flag in argv
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk"
    assert argv[argv.index("--permission-prompts") + 1] == "none"
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    # The built-in tool surface is reduced to the one tool that makes a
    # deferred MCP tool reachable at all.
    assert argv[argv.index("--tools") + 1] == "ToolSearch"
    assert argv[argv.index("--allowedTools") + 1] == f"ToolSearch,{PREFIX}*"
    # No user/project/local settings, so no hook can widen the policy.
    assert argv[argv.index("--setting-sources") + 1] == ""
    schema = json.loads(argv[argv.index("--json-schema") + 1])
    assert schema["properties"]["manifest_version"]["const"] == MANIFEST_VERSION


def test_the_ephemeral_settings_allow_only_the_design_mcp() -> None:
    permissions = settings_document()["permissions"]
    assert permissions["defaultMode"] == "dontAsk"
    assert set(permissions["allow"]) == {
        f"{PREFIX}*",
        "ToolSearch",
        "StructuredOutput",
    }
    assert "Bash" in permissions["deny"]


def test_only_the_result_emitter_is_admitted_beyond_the_requested_tools() -> None:
    """The harness injects `StructuredOutput` for `--json-schema`.

    It is admitted because it *is* the manifest channel, and nothing else
    from the built-in set rides in beside it.
    """
    assert HOST_BUILTIN_TOOLS == ("ToolSearch",)
    assert set(ALLOWED_BUILTIN_TOOLS) - set(HOST_BUILTIN_TOOLS) == {"StructuredOutput"}


def test_the_prompt_carries_only_allowlisted_context() -> None:
    request = _request()
    prompt = build_prompt(
        request, project_name="DDE checkout", mcp_server="claude-design"
    )
    assert "screens/checkout#hero" in prompt
    assert request.context.content_hash in prompt
    assert MANIFEST_PATH in prompt
    # It asks for design directions in token vocabulary, not for code.
    assert "Never emit a raw literal" in prompt


# --- certification of the run ------------------------------------------


@pytest.mark.asyncio
async def test_a_certified_run_normalizes_directions_onto_the_provider_contract(
    on_path: None,
) -> None:
    request = _request()
    host = FakeHost(generate=(0, _stream(_manifest(request))))
    artifacts = await _transport(host).generate(request)

    assert [item.direction_label for item in artifacts] == ["A", "B"]
    for artifact in artifacts:
        assert artifact.content["provider_project_id"] == PROJECT
        assert artifact.content["nodes"]
        assert "score" not in artifact.content
        assert "claude-design-mcp" in artifact.provider_version
        # Provenance records the account boundary, never the operator's
        # personal identifier.
        assert "example.com" not in artifact.provider_version


@pytest.mark.asyncio
async def test_a_stream_offering_a_tool_outside_the_allowlist_is_refused(
    on_path: None,
) -> None:
    """The flags are a claim; the stream is the evidence."""
    request = _request()
    stream = _stream(
        _manifest(request),
        tools=(*ALLOWED_BUILTIN_TOOLS, "Bash", f"{PREFIX}write_files"),
    )
    with pytest.raises(DdeError) as excinfo:
        await _transport(FakeHost(generate=(0, stream))).generate(request)
    assert excinfo.value.error_code == "POLICY_DENIED"
    assert excinfo.value.details["unexpected_tools"] == ["Bash"]


@pytest.mark.asyncio
async def test_a_non_allowlisted_tool_execution_is_refused(on_path: None) -> None:
    request = _request()
    manifest = _manifest(request)
    stream = _stream(
        manifest,
        calls=(
            ("Bash", {"command": "rm -rf /"}, False),
            (
                f"{PREFIX}write_files",
                {
                    "project_id": PROJECT,
                    "files": [
                        {"path": MANIFEST_PATH},
                        {"path": "direction-a.html"},
                        {"path": "direction-b.html"},
                    ],
                },
                False,
            ),
        ),
    )
    with pytest.raises(DdeError) as excinfo:
        await _transport(FakeHost(generate=(0, stream))).generate(request)
    assert excinfo.value.error_code == "POLICY_DENIED"
    assert excinfo.value.details["executed_tools"] == ["Bash"]


@pytest.mark.asyncio
async def test_a_run_whose_design_mcp_never_connected_is_unavailable(
    on_path: None,
) -> None:
    request = _request()
    stream = _stream(_manifest(request), mcp_servers=(("claude-design", "failed"),))
    with pytest.raises(DdeError) as excinfo:
        await _transport(FakeHost(generate=(0, stream))).generate(request)
    assert excinfo.value.error_code == "PROVIDER_UNAVAILABLE"
    assert excinfo.value.retryable is True


@pytest.mark.asyncio
async def test_a_denied_permission_invalidates_the_result(on_path: None) -> None:
    request = _request()
    stream = _stream(_manifest(request), permission_denials=("Bash",))
    with pytest.raises(DdeError) as excinfo:
        await _transport(FakeHost(generate=(0, stream))).generate(request)
    assert excinfo.value.error_code == "POLICY_DENIED"


@pytest.mark.asyncio
async def test_final_prose_is_never_the_contract(on_path: None) -> None:
    """A run that talks about three directions but returns no manifest is a
    provider error, not three directions."""
    request = _request()
    stream = _stream(None)
    with pytest.raises(DdeError) as excinfo:
        await _transport(FakeHost(generate=(0, stream))).generate(request)
    assert excinfo.value.error_code == "PROVIDER_ERROR"


@pytest.mark.asyncio
async def test_a_direction_cannot_target_an_exported_but_unmaterializable_node(
    on_path: None,
) -> None:
    request = _request()
    manifest = _manifest(request)
    manifest["directions"][0]["nodes"][0]["pxg_key"] = "screens/checkout"
    with pytest.raises(DdeError) as excinfo:
        await _transport(FakeHost(generate=(0, _stream(manifest)))).generate(request)
    assert excinfo.value.error_code == "PROVIDER_ERROR"
    assert excinfo.value.details["pxg_key"] == "screens/checkout"
    assert "materialize" in excinfo.value.message


@pytest.mark.asyncio
async def test_a_direction_about_an_unexported_node_is_refused(on_path: None) -> None:
    """The egress allowlist bounds what leaves; this bounds what comes back."""
    request = _request()
    manifest = _manifest(request)
    manifest["directions"][0]["nodes"][0]["pxg_key"] = "screens/admin#secret"
    with pytest.raises(DdeError) as excinfo:
        await _transport(FakeHost(generate=(0, _stream(manifest)))).generate(request)
    assert excinfo.value.error_code == "PROVIDER_ERROR"
    assert excinfo.value.details["pxg_key"] == "screens/admin#secret"


@pytest.mark.asyncio
async def test_a_direction_with_an_unknown_design_property_is_refused(
    on_path: None,
) -> None:
    request = _request()
    manifest = _manifest(request)
    manifest["directions"][0]["nodes"][0]["tokens"] = {
        "background": "--surface-card"
    }
    with pytest.raises(DdeError) as excinfo:
        await _transport(FakeHost(generate=(0, _stream(manifest)))).generate(request)
    assert excinfo.value.error_code == "PROVIDER_ERROR"
    assert excinfo.value.details["property"] == "background"


@pytest.mark.asyncio
async def test_a_direction_with_an_off_token_value_is_refused(on_path: None) -> None:
    request = _request()
    manifest = _manifest(request)
    manifest["directions"][0]["nodes"][0]["tokens"] = {"spacing": "24px"}
    with pytest.raises(DdeError) as excinfo:
        await _transport(FakeHost(generate=(0, _stream(manifest)))).generate(request)
    assert excinfo.value.error_code == "PROVIDER_ERROR"
    assert excinfo.value.details["property"] == "spacing"
    assert excinfo.value.details["value"] == "24px"


@pytest.mark.asyncio
async def test_a_direction_cannot_repeat_one_pxg_node(on_path: None) -> None:
    request = _request()
    manifest = _manifest(request)
    duplicate = dict(manifest["directions"][0]["nodes"][0])
    duplicate["tokens"] = {"spacing": "space2"}
    manifest["directions"][0]["nodes"].append(duplicate)
    with pytest.raises(DdeError) as excinfo:
        await _transport(FakeHost(generate=(0, _stream(manifest)))).generate(request)
    assert excinfo.value.error_code == "PROVIDER_ERROR"
    assert excinfo.value.details["pxg_key"] == "screens/checkout#hero"
    assert "ambiguous" in excinfo.value.message


@pytest.mark.asyncio
async def test_a_manifest_generated_against_another_snapshot_is_refused(
    on_path: None,
) -> None:
    request = _request()
    manifest = _manifest(request)
    manifest["design_system_hash"] = "0" * 64
    with pytest.raises(DdeError) as excinfo:
        await _transport(FakeHost(generate=(0, _stream(manifest)))).generate(request)
    assert excinfo.value.error_code == "PROVIDER_ERROR"


@pytest.mark.asyncio
async def test_a_direction_with_no_written_deliverable_is_refused(
    on_path: None,
) -> None:
    """A manifest entry with no observed write is a claim, not an artifact."""
    request = _request()
    manifest = _manifest(request)
    stream = _stream(
        manifest,
        calls=(
            (
                f"{PREFIX}write_files",
                {
                    "project_id": PROJECT,
                    "files": [{"path": MANIFEST_PATH}, {"path": "direction-a.html"}],
                },
                False,
            ),
        ),
    )
    with pytest.raises(DdeError) as excinfo:
        await _transport(FakeHost(generate=(0, stream))).generate(request)
    assert excinfo.value.error_code == "PROVIDER_ERROR"
    assert excinfo.value.details["missing_paths"] == ["direction-b.html"]


@pytest.mark.asyncio
async def test_a_failed_write_is_not_evidence_of_a_deliverable(on_path: None) -> None:
    request = _request()
    manifest = _manifest(request)
    paths = [MANIFEST_PATH, "direction-a.html", "direction-b.html"]
    stream = _stream(
        manifest,
        calls=(
            (
                f"{PREFIX}write_files",
                {"project_id": PROJECT, "files": [{"path": p} for p in paths]},
                True,
            ),
        ),
    )
    with pytest.raises(DdeError) as excinfo:
        await _transport(FakeHost(generate=(0, stream))).generate(request)
    assert excinfo.value.error_code == "PROVIDER_ERROR"
    assert excinfo.value.details["missing_paths"] == sorted(paths)


@pytest.mark.asyncio
async def test_a_timeout_keeps_its_own_state(on_path: None) -> None:
    request = _request()
    with pytest.raises(DdeError) as excinfo:
        await _transport(FakeHost(generate=(124, ""))).generate(request)
    assert excinfo.value.error_code == "PROVIDER_TIMEOUT"
    assert excinfo.value.retryable is True


# --- discovered provider state -----------------------------------------


@pytest.mark.asyncio
async def test_a_missing_executable_is_not_certified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "engine.studio.design.claude_transport.shutil.which", lambda name: None
    )
    status = await _transport(FakeHost()).status()
    assert status.state is ProviderState.NOT_CERTIFIED
    assert status.usable is False


@pytest.mark.asyncio
async def test_a_signed_out_host_asks_for_auth_rather_than_reporting_an_outage(
    on_path: None,
) -> None:
    host = FakeHost(auth=(0, json.dumps({"loggedIn": False})))
    status = await _transport(host).status()
    assert status.state is ProviderState.AUTH_REQUIRED
    assert "claude auth login" in status.detail


@pytest.mark.asyncio
async def test_a_disconnected_design_endpoint_is_unavailable(on_path: None) -> None:
    host = FakeHost(
        health=(
            0,
            "claude-design: https://api.anthropic.com/v1/design/mcp (HTTP) "
            "- ✘ Failed\n",
        )
    )
    status = await _transport(host).status()
    assert status.state is ProviderState.UNAVAILABLE


@pytest.mark.asyncio
async def test_a_certified_host_reports_its_discovered_identity(on_path: None) -> None:
    status = await _transport(FakeHost()).status()
    assert status.state is ProviderState.CERTIFIED
    assert status.usable is True
    assert status.version is not None
    assert "plan=max" in status.version
    assert "generate_directions" in status.capabilities


@pytest.mark.asyncio
async def test_status_is_cached_so_an_honest_poll_stays_cheap(on_path: None) -> None:
    """The cache must outlive the instance.

    A fresh `DesignGateway` -- and therefore a fresh transport -- is built
    per Gateway command, so an instance-scoped cache would spawn two probe
    subprocesses on every status poll.
    """
    host = FakeHost()
    config = ClaudeDesignTransportConfig(binary="claude")
    cache: dict = {}
    await ClaudeDesignMcpTransport(config, runner=host, cache=cache).status()
    await ClaudeDesignMcpTransport(config, runner=host, cache=cache).status()
    assert sum(1 for argv in host.invocations if "auth" in argv) == 1


# --- stream parsing ----------------------------------------------------


def test_unknown_events_do_not_break_the_parser() -> None:
    """A future harness event must not look like a design failure."""
    stream = (
        '{"type":"rate_limit_event","rate_limit_info":{}}\n'
        "not json at all\n"
        '{"type":"system","subtype":"init","tools":["ToolSearch"],'
        '"mcp_servers":[{"name":"claude-design","status":"connected"}]}\n'
        '{"type":"result","subtype":"success","is_error":false,'
        '"structured_output":{"ok":true}}\n'
    )
    observation = parse_stream(stream)
    assert observation.saw_result is True
    assert observation.mcp_servers == {"claude-design": "connected"}
    assert observation.structured_output == {"ok": True}
