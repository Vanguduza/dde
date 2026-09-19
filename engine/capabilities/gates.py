"""EDR-0019 Epic G capability-gate readiness.

Presence and configuration are not production readiness. `READY` is computed,
never asserted: it requires complete configuration, a live probe, the expected
identity, successful qualification and evidence that is still fresh. Evidence
that ages out demotes the gate to `STALE_EVIDENCE` rather than leaving it READY,
and a provider may never declare its own readiness.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from engine.core.errors import DdeError

READY = "READY"
STALE_EVIDENCE = "STALE_EVIDENCE"
DEGRADED = "DEGRADED"
BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"
BLOCKED_OWNER = "BLOCKED_OWNER"
REVOKED = "REVOKED"
UNCONFIGURED = "UNCONFIGURED"
CONFIGURED = "CONFIGURED"
REACHABLE = "REACHABLE"
QUALIFIED = "QUALIFIED"


@dataclass(frozen=True, slots=True)
class GateObservation:
    """Everything the readiness computation is allowed to look at."""

    configuration_state: str
    reachability_state: str
    qualification_state: str
    evidence_pointer: str | None
    last_probe_at: datetime | None
    expires_at: datetime | None
    revoked: bool = False
    owner_action_required: bool = False
    degraded_code: str | None = None
    identity_matches_expected: bool = True


@dataclass(frozen=True, slots=True)
class DegradedContract:
    """A degraded gate must say what still works, not merely that it is broken."""

    broken: str
    still_works: tuple[str, ...]
    will_not_do: tuple[str, ...]
    restore_action: str


def evidence_is_fresh(
    observation: GateObservation, *, now: datetime | None = None
) -> bool:
    if observation.evidence_pointer is None or observation.last_probe_at is None:
        return False
    if observation.expires_at is None:
        return True
    return (now or datetime.now(UTC)) < observation.expires_at


def compute_readiness(
    observation: GateObservation, *, now: datetime | None = None
) -> str:
    """Derive the readiness state. The only route to READY is full evidence."""
    if observation.revoked:
        return REVOKED
    if observation.owner_action_required:
        return BLOCKED_OWNER
    if observation.configuration_state != "COMPLETE":
        return (
            UNCONFIGURED if observation.configuration_state == "ABSENT" else CONFIGURED
        )
    if observation.reachability_state != "REACHABLE":
        return BLOCKED_EXTERNAL
    if not observation.identity_matches_expected:
        return DEGRADED
    if observation.qualification_state != "QUALIFIED":
        return REACHABLE
    if not evidence_is_fresh(observation, now=now):
        return STALE_EVIDENCE
    if observation.degraded_code:
        return DEGRADED
    return READY


def require_degraded_contract(
    readiness_state: str, contract: DegradedContract | None
) -> None:
    """A degraded gate without a contract is an unusable operator signal."""
    if readiness_state != DEGRADED:
        return
    if contract is None or not contract.broken or not contract.restore_action:
        raise DdeError(
            "VALIDATION_FAILED",
            "a DEGRADED capability gate must state broken/still_works/"
            "will_not_do/restore_action",
            retryable=False,
        )


def blocks_execution(readiness_state: str) -> bool:
    """Only READY and DEGRADED permit work; DEGRADED is bounded by its contract."""
    return readiness_state not in {READY, DEGRADED}
