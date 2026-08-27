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
    # ACTIVE -> READY is Chapter 7.4's warm-pool reuse: an environment may
    # serve multiple sequential runs of the same tenant and project, so it
    # returns to READY (pooled) between runs. The *eligibility* gate (workspace
    # destroyed, no credential material ever present, same tenant/project) is
    # enforced at the release() call site in engine.environments.service — this
    # table only permits the transition it encodes, exactly as Chapter 7.4's
    # "no run is scheduled into DRAINING or FAILED" rule lives in
    # assert_schedulable(), not here.
    "ACTIVE": frozenset({"DRAINING", "READY"}) | _ANY_TO_FAILED,
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

NOT_SCHEDULABLE: Final[frozenset[str]] = frozenset(
    {"DRAINING", "FAILED", "REPLACEMENT"}
)
