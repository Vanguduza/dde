"""Gateway scope model and command routing table (Chapter 14.2, 15.1, 15.4).

Baseline scopes come from the principal-class table in Chapter 14.2; a
session's requested scopes must be a subset of its `client_type` baseline.
`COMMAND_SCOPES` binds each gateway command to the scope required to execute
it, and `COMMAND_TARGET_TYPE` names the target kind a command must address.
Governance commands (`approval.batch_decide`,
`approval.request_budget_increase`, `approval.decide_budget_increase`) bind
the human `approval.decide` baseline for every decision and a separate
`approval.request` scope (human AND service baselines) for proposals;
neither binding grants decide authority to a non-human principal.
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
            # Propose-half only: a human may file a budget-increase
            # REQUEST for their own paused task (Ch.7.1/12.3); deciding
            # stays behind `approval.decide`. No decide authority is
            # widened by this scope.
            "approval.request",
            # Operator paste of static provider secrets (OpenSandbox API key)
            # through Studio Settings → Credential Broker capture seam.
            "credential.capture",
        }
    ),
    "service": frozenset(
        {
            "mission.read",
            "mission.control",
            "event.read",
            "approval.request",
            "credential.capture",
        }
    ),
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
    # Chapter 15.4 governance row: `POST /v1/approvals` · `/{id}/decision`
    # binds `approval.*`. Deciding is a human act (Ch.13.1: only a human
    # may hold `approval.decide`; Ch.13.2 forbids standing pre-authorisation
    # of exactly the classes a batch would most want to decide), so both
    # decide-shaped commands bind the human-only scope and a service
    # principal is refused at the session-authorisation layer.
    "approval.batch_decide": "approval.decide",
    "approval.decide_budget_increase": "approval.decide",
    # Requesting a budget increase (Ch.7.1/12.3 pause-for-human path) only
    # proposes a ceiling for human attention; the human still decides. The
    # new `approval.request` scope (added to human AND service baselines)
    # keeps the propose half available to service principals without
    # widening any decide authority. Fail-closed: unknown command types
    # still raise FORBIDDEN in `required_scope`.
    "approval.request_budget_increase": "approval.request",
    "credential.capture_opensandbox": "credential.capture",
    "credential.inspect_opensandbox": "credential.capture",
    # DDE-054 / Ch.14.2: minimal device command under device.command.
    # Richer device surface is EDR-0030 if product needs it.
    "device.heartbeat": "device.command",
}

#: Target kind each command must address (Chapter 15.2 target_type).
COMMAND_TARGET_TYPE: Final[dict[str, str]] = {
    "mission.create": "project",
    "mission.pause": "mission",
    "mission.resume": "mission",
    "mission.cancel": "mission",
    "mission.read": "mission",
    # Approvals and budget requests are project-scoped rows (Ch.3.2), so
    # the commands address the project and `_resolve_project` authorises
    # the principal grant for it directly.
    "approval.batch_decide": "project",
    "approval.request_budget_increase": "project",
    "approval.decide_budget_increase": "project",
    "credential.capture_opensandbox": "project",
    "credential.inspect_opensandbox": "project",
    "device.heartbeat": "device",
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
