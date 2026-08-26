"""DDE-055 messaging transport proofs (transport only, no authority).

Pins Ch.14.2 / Ch.15.1: messaging never imports engine, never requests
approval.decide, and control envelopes keep idempotency keys.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from interfaces.messaging.bridge import MessagingBridge
from interfaces.messaging.scopes import (
    FORBIDDEN_MESSAGING_SCOPES,
    MESSAGING_SCOPES,
    assert_messaging_scopes,
)
from interfaces.messaging.transport import InMemoryChannel

ROOT = Path(__file__).resolve().parents[2]
MESSAGING = ROOT / "interfaces" / "messaging"


def test_messaging_never_imports_engine() -> None:
    banned = ("from engine.", "import engine", "sqlalchemy", "asyncpg")
    offenders: list[str] = []
    for path in MESSAGING.rglob("*"):
        if path.suffix.lower() not in {".py", ".md"}:
            continue
        text = path.read_text(encoding="utf-8").lower()
        if any(token in text for token in banned):
            if path.name == "README.md" and "never" in text:
                continue
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_messaging_scopes_exclude_decide_and_capture() -> None:
    assert "approval.decide" not in MESSAGING_SCOPES
    assert "credential.capture" not in MESSAGING_SCOPES
    assert "approval.decide" in FORBIDDEN_MESSAGING_SCOPES
    assert_messaging_scopes(MESSAGING_SCOPES)
    with pytest.raises(PermissionError):
        assert_messaging_scopes(["mission.read", "approval.decide"])


class _FakeGateway:
    def __init__(self) -> None:
        self.posted: list[dict[str, Any]] = []
        self.opened_scopes: list[str] | None = None

    async def open_session(self, **kwargs: Any) -> str:
        self.opened_scopes = list(kwargs["scopes"])
        assert kwargs["client_type"] in {"human", "service"}
        assert "approval.decide" not in kwargs["scopes"]
        return "sess-msg-1"

    async def post_command(self, envelope: dict[str, Any]) -> dict[str, Any]:
        self.posted.append(envelope)
        return {"status": "accepted", "command_id": envelope["command_id"]}

    async def get_mission(self, **kwargs: Any) -> dict[str, Any]:
        return {"mission_id": kwargs["mission_id"], "status": "ACTIVE"}


@pytest.mark.asyncio
async def test_bridge_opens_allowlisted_scopes_only() -> None:
    channel = InMemoryChannel()
    gateway = _FakeGateway()
    bridge = MessagingBridge(channel, gateway, principal_id="p1")
    await bridge.connect()
    assert gateway.opened_scopes == list(MESSAGING_SCOPES)


@pytest.mark.asyncio
async def test_pause_keeps_idempotency_key_from_message_id() -> None:
    channel = InMemoryChannel()
    channel.push_inbound(message_id="m-42", text="pause mission-abc", sender_id="u1")
    gateway = _FakeGateway()
    bridge = MessagingBridge(channel, gateway, principal_id="p1")
    await bridge.connect()
    result = await bridge.poll_once()
    assert result is not None
    assert result["kind"] == "control"
    assert gateway.posted[0]["command_type"] == "mission.pause"
    assert gateway.posted[0]["idempotency_key"] == "msg-pause-m-42"
    assert gateway.posted[0]["target_id"] == "mission-abc"
    assert channel.outbound[0].text.startswith("mission.pause accepted")


@pytest.mark.asyncio
async def test_authority_verbs_refused() -> None:
    channel = InMemoryChannel()
    channel.push_inbound(message_id="m-9", text="approve approval-1", sender_id="u1")
    gateway = _FakeGateway()
    bridge = MessagingBridge(channel, gateway, principal_id="p1")
    await bridge.connect()
    with pytest.raises(PermissionError, match="refuses authority"):
        await bridge.poll_once()
    assert gateway.posted == []
