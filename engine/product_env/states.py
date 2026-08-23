"""ProductEnvironment lifecycle — Chapter 11.6's literal chain:

```
PROVISIONING -> MIGRATING -> SEEDING -> READY -> IN_USE -> TEARDOWN
(any pre-terminal state) -> FAILED -> TEARDOWN
```

`TEARDOWN` is terminal. Two deliberate shape decisions:

- There is no `FAILED -> MIGRATING` repair edge: Chapter 12.3 routes
  `ENVIRONMENT_FAILURE` to "replace environment, resume from checkpoint" —
  a failed provisioning side effect is torn down and replaced under a
  fresh identity, never blind-retried in place (Chapter 12.4).
- `TEARDOWN` is reachable from every pre-terminal state, not only
  `IN_USE`: a preview whose TTL expires mid-provisioning must still be
  destroyable by the TTL sweep (`teardown_expired`). Destruction is not a
  lifecycle success state; refusing it would strand un-destroyable rows.
"""

from __future__ import annotations

from typing import Final

from engine.core.errors import DdeError

PRODUCT_ENV_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "PROVISIONING": frozenset({"MIGRATING", "FAILED", "TEARDOWN"}),
    "MIGRATING": frozenset({"SEEDING", "FAILED", "TEARDOWN"}),
    "SEEDING": frozenset({"READY", "FAILED", "TEARDOWN"}),
    "READY": frozenset({"IN_USE", "FAILED", "TEARDOWN"}),
    "IN_USE": frozenset({"TEARDOWN", "FAILED"}),
    "FAILED": frozenset({"TEARDOWN"}),
    "TEARDOWN": frozenset(),
}

#: Terminal states: no outgoing mutation is legal from here.
TERMINAL_PRODUCT_ENV_STATES: Final[frozenset[str]] = frozenset({"TEARDOWN"})

#: States that may legally transition to FAILED.
PRE_TERMINAL_PRODUCT_ENV_STATES: Final[frozenset[str]] = frozenset(
    {"PROVISIONING", "MIGRATING", "SEEDING", "READY", "IN_USE"}
)


def assert_transition(current: str, target: str) -> None:
    """Refuse any transition outside the table at the mutation call site."""
    if target not in PRODUCT_ENV_TRANSITIONS.get(current, frozenset()):
        raise TransitionRefusedError(current, target)


class TransitionRefusedError(DdeError):
    """Typed refusal for an illegal ProductEnvironment transition.

    Carries the Chapter 15.5 VERSION_CONFLICT code directly so callers
    catch one exception type; `from`/`to` name both ends in `details`.
    """

    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            "VERSION_CONFLICT",
            f"Illegal ProductEnvironment transition {current} -> {target}",
            retryable=False,
            details={"from": current, "to": target},
        )
        self.current = current
        self.target = target
