"""Chapter 11.6 ProductEnvironment lifecycle — the explicit transition
table behind the state machine, mirrored on `engine.workers.states`.

The blueprint draws one linear chain with FAILED reachable from every
pre-terminal state:

```
PROVISIONING -> MIGRATING -> SEEDING -> READY -> IN_USE -> TEARDOWN
(any pre-terminal) -> FAILED -> TEARDOWN
```

There is deliberately no `FAILED -> MIGRATING` repair edge: Chapter 12.3's
`ENVIRONMENT_FAILURE` row says "replace environment, resume from
checkpoint" — recovery is teardown-plus-replacement under a fresh
identity, never an in-place blind retry of a failed provisioning side
effect.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Final

from engine.core.errors import DdeError
from engine.product_env.states import (
    PRODUCT_ENV_TRANSITIONS,
    TERMINAL_PRODUCT_ENV_STATES,
    assert_transition,
)

STATES: Final[tuple[str, ...]] = (
    "PROVISIONING",
    "MIGRATING",
    "SEEDING",
    "READY",
    "IN_USE",
    "TEARDOWN",
    "FAILED",
)


def _chain() -> Iterator[tuple[str, str]]:
    pairs = [
        ("PROVISIONING", "MIGRATING"),
        ("MIGRATING", "SEEDING"),
        ("SEEDING", "READY"),
        ("READY", "IN_USE"),
        ("IN_USE", "TEARDOWN"),
    ]
    return iter(pairs)


def test_happy_path_chain_is_legal_end_to_end() -> None:
    for current, target in _chain():
        assert_transition(current, target)


def test_failed_is_reachable_from_every_pre_terminal_state() -> None:
    for state in STATES:
        if state in TERMINAL_PRODUCT_ENV_STATES or state == "FAILED":
            continue
        assert "FAILED" in PRODUCT_ENV_TRANSITIONS[state], state


def test_failed_only_exits_through_teardown() -> None:
    assert PRODUCT_ENV_TRANSITIONS["FAILED"] == frozenset({"TEARDOWN"})


def test_teardown_is_terminal() -> None:
    assert PRODUCT_ENV_TRANSITIONS["TEARDOWN"] == frozenset()
    assert TERMINAL_PRODUCT_ENV_STATES == frozenset({"TEARDOWN"})


def test_backward_and_skipping_transitions_are_illegal() -> None:
    illegal = [
        ("READY", "MIGRATING"),
        ("READY", "PROVISIONING"),
        ("IN_USE", "SEEDING"),
        ("SEEDING", "MIGRATING"),
        ("PROVISIONING", "READY"),
        ("PROVISIONING", "IN_USE"),
        ("IN_USE", "MIGRATING"),
        ("MIGRATING", "PROVISIONING"),
        ("READY", "SEEDING"),
    ]
    for current, target in illegal:
        try:
            assert_transition(current, target)
        except DdeError:
            continue
        raise AssertionError(f"{current} -> {target} must be refused")


def test_illegal_transition_error_is_typed_and_names_both_ends() -> None:
    try:
        assert_transition("READY", "MIGRATING")
    except DdeError as error:
        assert error.error_code == "VERSION_CONFLICT"
        assert error.details is not None
        assert error.details.get("from") == "READY"
        assert error.details.get("to") == "MIGRATING"
    else:
        raise AssertionError("illegal transition must raise")


def test_every_declared_target_is_itself_a_known_state() -> None:
    for targets in PRODUCT_ENV_TRANSITIONS.values():
        assert targets <= frozenset(STATES)
