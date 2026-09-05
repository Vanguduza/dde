from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from engine.contracts.ai_conversation_policy import AiConversationPolicy
from engine.core.errors import DdeError
from engine.fabric.acp import AcpClient
from engine.fabric.automations import condition_matches, next_cron_at, next_run_at
from engine.fabric.interop import discover_local_harnesses, endpoint_config_hash
from engine.fabric.policies import policy_hash
from engine.fabric.skills import skill_manifest_hash
from engine.fabric.teams import validate_child_budget
from engine.gateway.scopes import (
    FABRIC_COMMAND_TYPES,
    required_scope,
    required_target_type,
)


def _policy(**overrides: object) -> AiConversationPolicy:
    now = datetime.now(UTC)
    values: dict[str, object] = {
        "policy_id": uuid4(),
        "tenant_id": uuid4(),
        "project_id": uuid4(),
        "name": "quality",
        "reasoning_effort": "DEEP",
        "permission_profile": "APPROVAL_GATED",
        "toolset_ids": ["repository"],
        "allowed_capability_ids": ["capability.repository"],
        "denied_capability_ids": [],
        "fallback_chain": [],
        "max_turns": 20,
        "context_token_budget": 24000,
        "cost_budget_usd": 5.0,
        "quality_priority": 95,
        "latency_priority": 20,
        "independent_review_required": True,
        "created_by": uuid4(),
        "lock_version": 1,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return AiConversationPolicy.model_validate(values)


def test_policy_hash_is_stable_and_sensitive_to_policy() -> None:
    policy = _policy()
    assert policy_hash(policy) == policy_hash(policy.model_copy())
    changed = policy.model_copy(update={"reasoning_effort": "MAXIMUM"})
    assert policy_hash(policy) != policy_hash(changed)


def test_team_budget_cannot_escalate_child() -> None:
    validate_child_budget(
        {"cost_usd": 10, "tokens": 10000}, {"cost_usd": 4, "tokens": 5000}
    )
    with pytest.raises(DdeError) as exc_info:
        validate_child_budget({"cost_usd": 10}, {"cost_usd": 11})
    assert exc_info.value.error_code == "BUDGET_EXCEEDED"


def test_skill_manifest_hash_is_order_normalized_and_content_sensitive() -> None:
    first = skill_manifest_hash(
        instructions="Inspect only",
        capabilities=["b", "a"],
        toolsets=["repo", "tests"],
        source_ref="repo:skill",
    )
    second = skill_manifest_hash(
        instructions="Inspect only",
        capabilities=["a", "b"],
        toolsets=["tests", "repo"],
        source_ref="repo:skill",
    )
    assert first == second
    assert first != skill_manifest_hash(
        instructions="Mutate",
        capabilities=["a", "b"],
        toolsets=["tests", "repo"],
        source_ref="repo:skill",
    )


def test_condition_and_schedule_evaluation_is_deterministic() -> None:
    context = {"ci": {"state": "green"}, "count": 4}
    assert condition_matches(
        {"path": "ci.state", "op": "eq", "value": "green"}, context
    )
    assert not condition_matches({"path": "count", "op": "gt", "value": 10}, context)
    now = datetime(2026, 9, 5, 8, 0, tzinfo=UTC)
    interval = next_run_at("INTERVAL", "3600", now=now, timezone="UTC")
    assert interval is not None
    assert interval > now
    assert next_cron_at("0 9 * * *", after=now, timezone="UTC").hour == 9


@pytest.mark.asyncio
async def test_discovery_never_upgrades_installed_capability_to_certification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "engine.fabric.interop.shutil.which", lambda name: f"/opt/{name}"
    )

    async def runner(argv: tuple[str, ...]) -> tuple[int, str, str]:
        if argv[-1] == "--version":
            return 0, f"{Path(argv[0]).name} 1.0\n", ""
        if argv[-3:] == ("--ignore-rules", "acp", "--check"):
            return 0, "Hermes ACP check OK", ""
        name = Path(argv[0]).name
        if name == "claude":
            return (
                0,
                (
                    "--session-id --resume --fork-session stream-json --json-schema "
                    "--model --effort --fallback-model --allowedTools --agents "
                    "--include-hook-events --mcp-config --background --file "
                    "--dangerously-skip-permissions"
                ),
                "",
            )
        if name == "hermes":
            return (
                0,
                (
                    "--resume --reasoning --model --provider fallback --skills "
                    "--toolsets --worktree hooks cron memory mcp acp "
                    "--ignore-rules --yolo"
                ),
                "",
            )
        return (
            0,
            (
                "resume fork --model --sandbox mcp --image --search "
                "dangerously-bypass-approvals"
            ),
            "",
        )

    probes = await discover_local_harnesses(runner)
    by_name = {item.harness_id: item for item in probes}
    assert by_name["hermes"].protocol == "ACP"
    assert by_name["hermes"].discovered_capabilities["acp"] is True
    assert by_name["hermes"].discovered_capabilities["dde_managed_context_mode"] is True
    assert (
        by_name["claude"].discovered_capabilities["requires_per_invocation_approval"]
        is True
    )
    assert "certified" not in by_name["hermes"].discovered_capabilities
    assert endpoint_config_hash(by_name["hermes"]) != endpoint_config_hash(
        by_name["claude"]
    )


def test_every_fabric_command_is_explicitly_mission_scoped() -> None:
    assert FABRIC_COMMAND_TYPES
    for command in FABRIC_COMMAND_TYPES:
        assert required_scope(command) == "mission.control"
        assert required_target_type(command) == "mission"
    with pytest.raises(DdeError):
        required_scope("frontend.fabric.secret_backdoor")


_FAKE_ACP = r"""
import json, sys
sid = "fake-session"
def send(value):
    print(json.dumps(value), flush=True)
for line in sys.stdin:
    msg = json.loads(line)
    method = msg.get("method")
    mid = msg.get("id")
    if method == "initialize":
        send({"jsonrpc":"2.0","id":mid,"result":{"protocolVersion":1,"agentCapabilities":{}}})
    elif method == "session/new":
        send({"jsonrpc":"2.0","id":mid,"result":{"sessionId":sid}})
    elif method == "session/resume":
        send({"jsonrpc":"2.0","id":mid,"result":{}})
    elif method == "session/prompt":
        send({"jsonrpc":"2.0","method":"session/update","params":{"sessionId":sid,
            "update":{"sessionUpdate":"agent_thought_chunk",
            "content":{"type":"text","text":"reason "}}}})
        send({"jsonrpc":"2.0","method":"session/update","params":{"sessionId":sid,
            "update":{"sessionUpdate":"agent_message_chunk",
            "content":{"type":"text","text":"answer"}}}})
        send({"jsonrpc":"2.0","id":mid,"result":{"stopReason":"end_turn"}})
    elif method in ("session/cancel", "session/close"):
        send({"jsonrpc":"2.0","id":mid,"result":{}})
"""


@pytest.mark.asyncio
async def test_acp_client_streams_session_without_implicit_permissions(
    tmp_path: Path,
) -> None:
    client = AcpClient((sys.executable, "-u", "-c", _FAKE_ACP), cwd=tmp_path)
    try:
        session_id = await client.new_session()
        result = await client.prompt(session_id, "hello")
        assert session_id == "fake-session"
        assert result.text == "answer"
        assert result.reasoning == "reason "
        assert result.stop_reason == "end_turn"
    finally:
        await client.close()


_FAKE_ACP_ESCAPE = r"""
import json, sys
sid="escape"
def send(v): print(json.dumps(v), flush=True)
for line in sys.stdin:
    msg=json.loads(line); m=msg.get("method"); i=msg.get("id")
    if m=="initialize": send({"jsonrpc":"2.0","id":i,"result":{"protocolVersion":1}})
    elif m=="session/new": send({"jsonrpc":"2.0","id":i,"result":{"sessionId":sid}})
    elif m=="session/prompt":
        send({"jsonrpc":"2.0","id":900,"method":"fs/read_text_file","params":{"sessionId":sid,"path":"/etc/passwd"}})
        response=json.loads(sys.stdin.readline())
        text="blocked" if "error" in response else "escaped"
        send({"jsonrpc":"2.0","method":"session/update","params":{"sessionId":sid,"update":{"sessionUpdate":"agent_message_chunk","content":{"type":"text","text":text}}}})
        send({"jsonrpc":"2.0","id":i,"result":{"stopReason":"end_turn"}})
"""


@pytest.mark.asyncio
async def test_acp_file_bridge_rejects_path_escape(tmp_path: Path) -> None:
    client = AcpClient((sys.executable, "-u", "-c", _FAKE_ACP_ESCAPE), cwd=tmp_path)
    try:
        sid = await client.new_session()
        result = await client.prompt(sid, "read outside")
        assert result.text == "blocked"
    finally:
        await client.close()
