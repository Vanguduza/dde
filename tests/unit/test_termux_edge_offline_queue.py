"""DDE-054 Termux edge: device scopes + offline queue proofs.

Pins Ch.14.2 device baseline and Ch.13.7 offline-queue behaviour the
Termux client must implement. Does not claim WS/SSE replay (EDR-0027).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from interfaces.termux.device_client import DEVICE_SCOPES, DeviceClient
from interfaces.termux.offline_queue import (
    OfflineQueue,
    QueuedCommand,
    offline_queue_enabled,
)

ROOT = Path(__file__).resolve().parents[2]
TERMUX = ROOT / "interfaces" / "termux"


def test_termux_never_imports_engine() -> None:
    banned = ("from engine.", "import engine", "sqlalchemy", "asyncpg")
    offenders: list[str] = []
    for path in TERMUX.rglob("*"):
        if path.suffix.lower() not in {".py", ".md"}:
            continue
        text = path.read_text(encoding="utf-8").lower()
        if any(token in text for token in banned):
            if path.name == "README.md" and "never" in text:
                continue
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_device_scopes_exclude_mission() -> None:
    assert "mission.read" not in DEVICE_SCOPES
    assert "mission.control" not in DEVICE_SCOPES
    assert set(DEVICE_SCOPES) == {"device.read", "device.command"}


def test_offline_queue_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DDE_ANDROID_OFFLINE_QUEUE_ENABLED", raising=False)
    assert offline_queue_enabled() is False


def test_offline_queue_persists_idempotency_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DDE_ANDROID_OFFLINE_QUEUE_ENABLED", "true")
    queue = OfflineQueue(tmp_path / "queue.jsonl")
    cmd = QueuedCommand(
        command_id="cmd-1",
        idempotency_key="idem-1",
        command_type="device.heartbeat",
        target_type="device",
        target_id="dev-1",
        parameters={},
        principal_id="prin-1",
        client_session_id="sess-1",
    )
    queue.enqueue(cmd)
    pending = queue.pending()
    assert len(pending) == 1
    assert pending[0].idempotency_key == "idem-1"
    assert pending[0].command_id == "cmd-1"


class _FakeTransport:
    def __init__(self) -> None:
        self.posted: list[dict[str, Any]] = []
        self.fail_once = False

    async def open_session(self, **kwargs: Any) -> str:
        assert kwargs["client_type"] == "device"
        assert kwargs["scopes"] == list(DEVICE_SCOPES)
        assert kwargs["device_id"]
        return "sess-device-1"

    async def resume_session(self, **kwargs: Any) -> dict[str, Any]:
        return {"session_id": kwargs["session_id"], "fresh_snapshot": True}

    async def post_command(self, envelope: dict[str, Any]) -> dict[str, Any]:
        if self.fail_once:
            self.fail_once = False
            raise ConnectionError("offline")
        self.posted.append(envelope)
        return {"status": "accepted", "command_id": envelope["command_id"]}


@pytest.mark.asyncio
async def test_heartbeat_enqueues_when_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DDE_ANDROID_OFFLINE_QUEUE_ENABLED", "true")
    transport = _FakeTransport()
    queue = OfflineQueue(tmp_path / "queue.jsonl")
    client = DeviceClient(transport, queue, principal_id="p1", device_id="d1")
    await client.connect()
    result = await client.heartbeat(online=False)
    assert result is None
    pending = queue.pending()
    assert len(pending) == 1
    assert pending[0].command_type == "device.heartbeat"


@pytest.mark.asyncio
async def test_flush_preserves_keys_and_drains(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DDE_ANDROID_OFFLINE_QUEUE_ENABLED", "true")
    transport = _FakeTransport()
    queue = OfflineQueue(tmp_path / "queue.jsonl")
    client = DeviceClient(transport, queue, principal_id="p1", device_id="d1")
    await client.connect()
    await client.heartbeat(online=False)
    key = queue.pending()[0].idempotency_key
    results = await client.flush_offline()
    assert len(results) == 1
    assert transport.posted[0]["idempotency_key"] == key
    assert queue.pending() == []
