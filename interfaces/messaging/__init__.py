"""Messaging transport surface (DDE-055) — transport only, no authority."""

from __future__ import annotations

__all__ = [
    "MESSAGING_SCOPES",
    "FORBIDDEN_MESSAGING_SCOPES",
    "MessagingBridge",
    "InMemoryChannel",
]

from interfaces.messaging.bridge import MessagingBridge
from interfaces.messaging.scopes import FORBIDDEN_MESSAGING_SCOPES, MESSAGING_SCOPES
from interfaces.messaging.transport import InMemoryChannel
