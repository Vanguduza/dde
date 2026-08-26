"""Durable offline command queue for the Termux device edge (DDE-054).

Armed only when ``android.offline_queue.enabled`` (env
``DDE_ANDROID_OFFLINE_QUEUE_ENABLED``) is true. Enqueued envelopes keep
their ``command_id`` / ``idempotency_key`` so reconnect flush cannot
mint a second mutation.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def offline_queue_enabled() -> bool:
    raw = os.environ.get("DDE_ANDROID_OFFLINE_QUEUE_ENABLED", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class QueuedCommand:
    command_id: str
    idempotency_key: str
    command_type: str
    target_type: str
    target_id: str
    parameters: dict[str, Any]
    principal_id: str
    client_session_id: str
    protocol_version: str = "1"

    def to_envelope(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "idempotency_key": self.idempotency_key,
            "principal_id": self.principal_id,
            "client_session_id": self.client_session_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "command_type": self.command_type,
            "parameters": self.parameters,
            "protocol_version": self.protocol_version,
        }

    @classmethod
    def from_envelope(cls, envelope: dict[str, Any]) -> QueuedCommand:
        return cls(
            command_id=str(envelope["command_id"]),
            idempotency_key=str(envelope["idempotency_key"]),
            command_type=str(envelope["command_type"]),
            target_type=str(envelope["target_type"]),
            target_id=str(envelope["target_id"]),
            parameters=dict(envelope.get("parameters") or {}),
            principal_id=str(envelope["principal_id"]),
            client_session_id=str(envelope["client_session_id"]),
            protocol_version=str(envelope.get("protocol_version") or "1"),
        )


class OfflineQueue:
    """Append-only JSONL queue on local disk (Termux-home friendly)."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def enqueue(self, command: QueuedCommand) -> None:
        if not offline_queue_enabled():
            raise RuntimeError(
                "Offline queue disabled (DDE_ANDROID_OFFLINE_QUEUE_ENABLED)"
            )
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(command.to_envelope(), sort_keys=True))
            handle.write("\n")

    def pending(self) -> list[QueuedCommand]:
        if not self._path.exists():
            return []
        out: list[QueuedCommand] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            out.append(QueuedCommand.from_envelope(json.loads(line)))
        return out

    def replace_all(self, remaining: list[QueuedCommand]) -> None:
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            for command in remaining:
                handle.write(json.dumps(command.to_envelope(), sort_keys=True))
                handle.write("\n")
        tmp.replace(self._path)
