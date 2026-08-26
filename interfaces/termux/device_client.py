"""Gateway device client for Termux edge (DDE-054).

Opens ``client_type=device`` sessions only. Mission scopes are never
requested. Heartbeats go through ``POST /v1/commands`` with
``command_type=device.heartbeat`` when online; otherwise they enqueue
via :class:`OfflineQueue`.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import uuid4

from interfaces.termux.offline_queue import (
    OfflineQueue,
    QueuedCommand,
    offline_queue_enabled,
)

DEVICE_SCOPES = ("device.read", "device.command")


class GatewayTransport(Protocol):
    async def open_session(
        self,
        *,
        principal_id: str,
        client_type: str,
        device_id: str,
        scopes: list[str],
    ) -> str: ...

    async def resume_session(
        self,
        *,
        session_id: str,
        last_event_at: str | None,
    ) -> dict[str, Any]: ...

    async def post_command(self, envelope: dict[str, Any]) -> dict[str, Any]: ...


class DeviceClient:
    def __init__(
        self,
        transport: GatewayTransport,
        queue: OfflineQueue,
        *,
        principal_id: str,
        device_id: str,
        project_id: str,
    ) -> None:
        self._transport = transport
        self._queue = queue
        self._principal_id = principal_id
        self._device_id = device_id
        self._project_id = project_id
        self.session_id: str | None = None

    async def connect(self) -> str:
        session_id = await self._transport.open_session(
            principal_id=self._principal_id,
            client_type="device",
            device_id=self._device_id,
            scopes=list(DEVICE_SCOPES),
        )
        self.session_id = session_id
        return session_id

    async def resume(self, *, last_event_at: str | None = None) -> dict[str, Any]:
        """Ch.15.1 reconnect — caller must treat fresh_snapshot as authority
        and discard any unconfirmed local projection before flush."""
        if self.session_id is None:
            raise RuntimeError("DeviceClient.connect() required first")
        return await self._transport.resume_session(
            session_id=self.session_id,
            last_event_at=last_event_at,
        )

    def _heartbeat_envelope(self) -> QueuedCommand:
        if self.session_id is None:
            raise RuntimeError("DeviceClient.connect() required first")
        command_id = str(uuid4())
        idempotency_key = f"device-heartbeat-{command_id}"
        return QueuedCommand(
            command_id=command_id,
            idempotency_key=idempotency_key,
            command_type="device.heartbeat",
            target_type="device",
            target_id=self._device_id,
            parameters={"project_id": self._project_id},
            principal_id=self._principal_id,
            client_session_id=self.session_id,
        )

    async def heartbeat(self, *, online: bool) -> dict[str, Any] | None:
        envelope = self._heartbeat_envelope()
        if not online:
            if not offline_queue_enabled():
                raise RuntimeError("offline and queue disabled")
            self._queue.enqueue(envelope)
            return None
        return await self._transport.post_command(envelope.to_envelope())

    async def flush_offline(self) -> list[dict[str, Any]]:
        """Drain queue oldest-first; preserves command_id / idempotency_key.

        Resume is the caller's responsibility (see :meth:`resume`) before
        flush so Ch.15.1 fresh-snapshot re-sync happens first.
        """
        pending = self._queue.pending()
        results: list[dict[str, Any]] = []
        for index, command in enumerate(pending):
            try:
                results.append(
                    await self._transport.post_command(command.to_envelope())
                )
            except Exception:
                self._queue.replace_all(pending[index:])
                return results
        self._queue.replace_all([])
        return results

    async def reconnect_and_flush(
        self, *, last_event_at: str | None = None
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Resume then flush — never invents new idempotency keys."""
        snapshot = await self.resume(last_event_at=last_event_at)
        return snapshot, await self.flush_offline()
