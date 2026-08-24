"""Chapter 4.3 planning registries' lifecycles.

Mission template registry (Chapter 4.3: "first-class registry objects
with their own version and conformance tests"):

```
ACTIVE -> RETIRED
```

A MissionTemplate is registered ACTIVE; it leaves the active set only by
retirement. Chapter 3.10 governs change: a material change registers a
NEW `template_version` content-hashed over the template fields -- there
is no edit edge, because graphs already instantiated from a version must
stay explainable by the exact definition that produced them. RETIRED is
terminal: un-retiring would silently re-attach old decomposition
semantics under a key consumers already stopped trusting.

Plan-draft lifecycle (Chapter 4.3 determinism split):

```
PROPOSED -> VALIDATED | REJECTED
VALIDATED -> PROMOTED
```

A draft arrives as untrusted model output in PROPOSED. The deterministic
validator moves it to VALIDATED or REJECTED and records typed refusals;
only a VALIDATED draft may be promoted, and promotion means the draft's
nodes landed as a REAL TaskGraph through the ordinary DRAFT ->
VALIDATING -> APPROVED|REJECTED gate -- the draft itself never becomes
executable. PROMOTED/REJECTED are terminal.
"""

from __future__ import annotations

from typing import Final

from engine.core.errors import DdeError

TEMPLATE_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "ACTIVE": frozenset({"RETIRED"}),
    "RETIRED": frozenset(),
}

TERMINAL_TEMPLATE_STATES: Final[frozenset[str]] = frozenset({"RETIRED"})

DRAFT_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "PROPOSED": frozenset({"VALIDATED", "REJECTED"}),
    "VALIDATED": frozenset({"PROMOTED"}),
    "REJECTED": frozenset(),
    "PROMOTED": frozenset(),
}

TERMINAL_DRAFT_STATES: Final[frozenset[str]] = frozenset({"PROMOTED", "REJECTED"})


def assert_template_transition(current: str, target: str) -> None:
    if target not in TEMPLATE_TRANSITIONS.get(current, frozenset()):
        raise TemplateTransitionError(current, target)


def assert_draft_transition(current: str, target: str) -> None:
    if target not in DRAFT_TRANSITIONS.get(current, frozenset()):
        raise DraftTransitionError(current, target)


class TemplateTransitionError(DdeError):
    """Typed refusal for an illegal MissionTemplate lifecycle transition."""

    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            "VERSION_CONFLICT",
            f"Illegal MissionTemplate transition {current} -> {target}",
            retryable=False,
            details={"from": current, "to": target},
        )
        self.current = current
        self.target = target


class DraftTransitionError(DdeError):
    """Typed refusal for an illegal PlanDraft lifecycle transition."""

    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            "VERSION_CONFLICT",
            f"Illegal PlanDraft transition {current} -> {target}",
            retryable=False,
            details={"from": current, "to": target},
        )
        self.current = current
        self.target = target
