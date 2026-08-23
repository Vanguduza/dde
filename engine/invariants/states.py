"""Chapter 11.5 definition lifecycle — deliberately minimal:

```
ACTIVE -> RETIRED
```

A DomainInvariant is declared ACTIVE at registration; it leaves the
active set only by retirement. Chapter 3.10 governs change: a material
change registers a NEW definition version content-hashed over the
definition fields — there is no DRAFT->APPROVED authoring workflow to
model, and no edit edge, because evaluations always record the
`definition_version` they ran against.

`RETIRED` is terminal: un-retiring would silently re-attach old
semantics to new evaluations under a name consumers already stopped
trusting. A retired invariant that is genuinely needed again is
re-declared as a fresh version with provenance.
"""

from __future__ import annotations

from typing import Final

from engine.core.errors import DdeError

DEFINITION_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "ACTIVE": frozenset({"RETIRED"}),
    "RETIRED": frozenset(),
}

#: Terminal states: no outgoing mutation is legal from here.
TERMINAL_DEFINITION_STATES: Final[frozenset[str]] = frozenset({"RETIRED"})


def assert_transition(current: str, target: str) -> None:
    """Refuse any transition outside the table at the mutation call site."""
    if target not in DEFINITION_TRANSITIONS.get(current, frozenset()):
        raise DefinitionTransitionError(current, target)


class DefinitionTransitionError(DdeError):
    """Typed refusal for an illegal DomainInvariant lifecycle transition.

    Carries the Chapter 15.5 VERSION_CONFLICT code directly so callers
    catch one exception type; `from`/`to` name both ends in `details`.
    """

    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            "VERSION_CONFLICT",
            f"Illegal DomainInvariant transition {current} -> {target}",
            retryable=False,
            details={"from": current, "to": target},
        )
        self.current = current
        self.target = target
