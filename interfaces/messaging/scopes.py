"""Allowlisted Gateway scopes for messaging transports (DDE-055).

Ch.14.2: messaging is transport only. It may observe and control missions
through the Gateway, but must never request ``approval.decide`` or
credential-capture scopes — those remain human / brokered surfaces.
"""

from __future__ import annotations

from typing import Final

#: Scopes a messaging session may request (subset of human/service baselines).
MESSAGING_SCOPES: Final[tuple[str, ...]] = (
    "mission.read",
    "mission.control",
)

#: Explicitly refused on this surface even if a baseline would allow them.
FORBIDDEN_MESSAGING_SCOPES: Final[frozenset[str]] = frozenset(
    {
        "approval.decide",
        "approval.request",
        "credential.capture",
        "mission.create",
        "device.command",
        "device.read",
        "worker.execute",
    }
)


def assert_messaging_scopes(scopes: list[str] | tuple[str, ...]) -> None:
    requested = set(scopes)
    if not requested.issubset(set(MESSAGING_SCOPES)):
        raise PermissionError(
            f"messaging scopes must be subset of {MESSAGING_SCOPES}; got {scopes}"
        )
    banned = requested & FORBIDDEN_MESSAGING_SCOPES
    if banned:
        raise PermissionError(f"messaging forbids scopes {sorted(banned)}")
