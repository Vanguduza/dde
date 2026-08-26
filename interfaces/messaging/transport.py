"""Channel transport Protocol + in-memory stub (DDE-055).

Vendor Slack/Telegram SDKs stay behind this Protocol (EDR-0031). The
in-memory channel exists so Gateway bridge proofs need no network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class InboundMessage:
    channel_id: str
    message_id: str
    text: str
    sender_id: str


@dataclass(frozen=True)
class OutboundMessage:
    channel_id: str
    text: str
    idempotency_key: str


class ChannelTransport(Protocol):
    async def receive(self) -> InboundMessage | None: ...

    async def send(self, message: OutboundMessage) -> None: ...


@dataclass
class InMemoryChannel:
    """Stub channel for unit proofs — FIFO inbound, append-only outbound."""

    channel_id: str = "mem-1"
    inbound: list[InboundMessage] = field(default_factory=list)
    outbound: list[OutboundMessage] = field(default_factory=list)

    async def receive(self) -> InboundMessage | None:
        if not self.inbound:
            return None
        return self.inbound.pop(0)

    async def send(self, message: OutboundMessage) -> None:
        self.outbound.append(message)

    def push_inbound(self, *, message_id: str, text: str, sender_id: str) -> None:
        self.inbound.append(
            InboundMessage(
                channel_id=self.channel_id,
                message_id=message_id,
                text=text,
                sender_id=sender_id,
            )
        )
