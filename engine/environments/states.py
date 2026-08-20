"""ExecutionEnvironment lifecycle (Chapter 7.3): "PROVISIONING -> READY ->
ACTIVE -> DRAINING -> RETIRED; any -> FAILED -> REPAIRING | REPLACEMENT."

Chapter 7.4 ("no run is scheduled into DRAINING or FAILED") is enforced by
`engine.environments.service.ExecutionEnvironmentService` checking
`lifecycle_state` before binding a workspace or running a command, not by
this table.
"""

from __future__ import annotations

from typing import Final

_ANY_TO_FAILED: Final[frozenset[str]] = frozenset({"FAILED"})

ENVIRONMENT_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "PROVISIONING": frozenset({"READY"}) | _ANY_TO_FAILED,
    "READY": frozenset({"ACTIVE", "DRAINING"}) | _ANY_TO_FAILED,
    "ACTIVE": frozenset({"DRAINING"}) | _ANY_TO_FAILED,
    "DRAINING": frozenset({"RETIRED"}) | _ANY_TO_FAILED,
    "RETIRED": frozenset(),
    # Chapter 7.3's diagram writes "FAILED -> REPAIRING | REPLACEMENT" as the
    # two ways out of a failure; REPLACEMENT is a terminal marker meaning
    # "this environment is abandoned, a new one replaces it", not a state
    # that itself resumes.
    "FAILED": frozenset({"REPAIRING", "REPLACEMENT"}),
    "REPAIRING": frozenset({"READY"}) | _ANY_TO_FAILED,
    "REPLACEMENT": frozenset(),
}

NOT_SCHEDULABLE: Final[frozenset[str]] = frozenset({"DRAINING", "FAILED"})
