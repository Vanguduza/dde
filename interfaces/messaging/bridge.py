"""Messaging ↔ Gateway bridge (DDE-055).

Parses a minimal command dialect from inbound channel text and posts
Gateway envelopes. Never imports engine; never requests forbidden scopes.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import uuid4

from interfaces.messaging.scopes import MESSAGING_SCOPES, assert_messaging_scopes
from interfaces.messaging.transport import ChannelTransport, OutboundMessage


class GatewayTransport(Protocol):
    async def open_session(
        self,
        *,
        principal_id: str,
        client_type: str,
        scopes: list[str],
    ) -> str: ...

    async def post_command(self, envelope: dict[str, Any]) -> dict[str, Any]: ...

    async def get_mission(
        self, *, session_id: str, principal_id: str, mission_id: str
    ) -> dict[str, Any]: ...


class MessagingBridge:
    """Transport-only bridge: channel text → Gateway, never authority."""

    def __init__(
        self,
        channel: ChannelTransport,
        gateway: GatewayTransport,
        *,
        principal_id: str,
        client_type: str = "service",
    ) -> None:
        assert_messaging_scopes(MESSAGING_SCOPES)
        if client_type not in {"human", "service"}:
            raise PermissionError(
                f"messaging client_type must be human or service (got {client_type!r})"
            )
        self._channel = channel
        self._gateway = gateway
        self._principal_id = principal_id
        self._client_type = client_type
        self.session_id: str | None = None

    async def connect(self) -> str:
        session_id = await self._gateway.open_session(
            principal_id=self._principal_id,
            client_type=self._client_type,
            scopes=list(MESSAGING_SCOPES),
        )
        self.session_id = session_id
        return session_id

    async def poll_once(self) -> dict[str, Any] | None:
        if self.session_id is None:
            raise RuntimeError("MessagingBridge.connect() required first")
        inbound = await self._channel.receive()
        if inbound is None:
            return None
        return await self._dispatch(inbound.text, message_id=inbound.message_id)

    async def _dispatch(self, text: str, *, message_id: str) -> dict[str, Any]:
        if self.session_id is None:
            raise RuntimeError("MessagingBridge.connect() required first")
        parts = text.strip().split()
        if not parts:
            return await self._reply("empty command", key=f"msg-empty-{message_id}")

        verb = parts[0].lower()
        if verb == "status" and len(parts) == 2:
            mission = await self._gateway.get_mission(
                session_id=self.session_id,
                principal_id=self._principal_id,
                mission_id=parts[1],
            )
            status = str(mission.get("status", "UNKNOWN"))
            await self._channel.send(
                OutboundMessage(
                    channel_id=getattr(self._channel, "channel_id", "unknown"),
                    text=f"mission {parts[1]} status={status}",
                    idempotency_key=f"msg-status-{message_id}",
                )
            )
            return {"kind": "status", "mission": mission}

        if verb in {"pause", "resume", "cancel"} and len(parts) == 2:
            command_type = f"mission.{verb}"
            command_id = str(uuid4())
            envelope = {
                "command_id": command_id,
                "idempotency_key": f"msg-{verb}-{message_id}",
                "principal_id": self._principal_id,
                "client_session_id": self.session_id,
                "target_type": "mission",
                "target_id": parts[1],
                "command_type": command_type,
                "parameters": {},
                "protocol_version": "1",
            }
            acceptance = await self._gateway.post_command(envelope)
            await self._channel.send(
                OutboundMessage(
                    channel_id=getattr(self._channel, "channel_id", "unknown"),
                    text=(
                        f"{command_type} accepted "
                        f"command_id={acceptance.get('command_id', command_id)}"
                    ),
                    idempotency_key=f"msg-{verb}-ack-{message_id}",
                )
            )
            return {"kind": "control", "acceptance": acceptance}

        if verb in {"approve", "decide", "capture-secret"}:
            raise PermissionError(
                "messaging transport refuses authority verbs "
                f"{verb!r} (no approval.decide / credential.capture)"
            )

        return await self._reply(
            f"unknown command {verb!r}",
            key=f"msg-unknown-{message_id}",
        )

    async def _reply(self, text: str, *, key: str) -> dict[str, Any]:
        await self._channel.send(
            OutboundMessage(
                channel_id=getattr(self._channel, "channel_id", "unknown"),
                text=text,
                idempotency_key=key,
            )
        )
        return {"kind": "reply", "text": text}
