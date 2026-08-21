"""Gateway scope model and command routing table (Chapter 14.2, 15.1, 15.4).

Baseline scopes come from the principal-class table in Chapter 14.2; a
session's requested scopes must be a subset of its `client_type` baseline.
`COMMAND_SCOPES` binds each gateway command to the scope required to execute
it, and `COMMAND_TARGET_TYPE` names the target kind a command must address.
"""

from __future__ import annotations

from typing import Final

from engine.core.errors import DdeError

#: Baseline scopes granted per principal class (Chapter 14.2).
BASELINE_SCOPES: Final[dict[str, frozenset[str]]] = {
    "human": frozenset(
        {
            "mission.read",
            "mission.create",
            "mission.control",
            "approval.read",
            "approval.decide",
        }
    ),
    "service": frozenset({"mission.read", "mission.control", "event.read"}),
    "worker": frozenset({"worker.execute", "worker.events", "worker.artifacts"}),
    "device": frozenset({"device.read", "device.command"}),
    "capability": frozenset({"capability.execute"}),
}

#: Scope required by each gateway command (Chapter 15.4 "Scope" column).
COMMAND_SCOPES: Final[dict[str, str]] = {
    "mission.create": "mission.create",
    "mission.pause": "mission.control",
    "mission.resume": "mission.control",
    "mission.cancel": "mission.control",
    "mission.read": "mission.read",
}

#: Target kind each command must address (Chapter 15.2 target_type).
COMMAND_TARGET_TYPE: Final[dict[str, str]] = {
    "mission.create": "project",
    "mission.pause": "mission",
    "mission.resume": "mission",
    "mission.cancel": "mission",
    "mission.read": "mission",
}

#: Mission control command -> target mission status (Chapter 4.8).
MISSION_CONTROL_TARGETS: Final[dict[str, str]] = {
    "mission.pause": "PAUSED",
    "mission.resume": "ACTIVE",
    "mission.cancel": "CANCELLED",
}


def required_scope(command_type: str) -> str:
    if command_type not in COMMAND_SCOPES:
        raise DdeError(
            "FORBIDDEN",
            "Unsupported command_type",
            details={"command_type": command_type},
        )
    return COMMAND_SCOPES[command_type]


def required_target_type(command_type: str) -> str:
    return COMMAND_TARGET_TYPE[command_type]
