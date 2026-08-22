"""Chapter 13.7 configuration validation — a startup gate.

The process must refuse to start when a dangerous combination is reachable
in any environment class other than `development`. Flags this mission does
not yet own (learning canaries, semantic retrievers, merge-queue
concurrency wiring) are accepted as unset/default-safe and still checked
when a caller actually supplies them.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.core.errors import DdeError

DEVELOPMENT = "development"


@dataclass(frozen=True)
class RuntimeFlags:
    environment_class: str = DEVELOPMENT
    capability_enforcement_mode: str = "strict"
    autonomy_default_ceiling: int = 2
    routing_mode: str = "deterministic"
    routing_exploration_epsilon: float = 0.0
    merge_queue_concurrency: int = 1
    mission_oracle_policy_configured: bool = False
    routing_policy_artifact_certified: bool = False
    #: Chapter 6.1 gate-5 note / §6.3 adoption: development-only degraded
    #: default when no legal candidate survives a capacity/availability
    # - class failure. Never legal outside `development`.
    routing_degraded_default: bool = False


def validate_configuration(flags: RuntimeFlags) -> None:
    """Chapter 13.7: a dangerous combination must be impossible to reach
    by editing a value. Raises POLICY_DENIED; does not coerce."""
    if flags.environment_class == DEVELOPMENT:
        return
    if flags.routing_degraded_default:
        raise DdeError(
            "POLICY_DENIED",
            "routing.degraded_default is legal only in the development "
            "environment class",
            retryable=False,
            details={"environment_class": flags.environment_class},
        )
    if flags.capability_enforcement_mode == "audit_only":
        raise DdeError(
            "POLICY_DENIED",
            "capability.enforcement.mode=audit_only is rejected outside development",
            retryable=False,
            details={"environment_class": flags.environment_class},
        )
    if (
        flags.autonomy_default_ceiling >= 4
        and not flags.mission_oracle_policy_configured
    ):
        raise DdeError(
            "POLICY_DENIED",
            "autonomy.default_ceiling >= 4 requires a configured mission oracle policy",
            retryable=False,
            details={"autonomy_default_ceiling": flags.autonomy_default_ceiling},
        )
    if flags.routing_mode == "promoted_historical" and not (
        flags.routing_policy_artifact_certified
    ):
        raise DdeError(
            "POLICY_DENIED",
            "routing.mode=promoted_historical requires a certified policy artifact",
            retryable=False,
        )
    if flags.merge_queue_concurrency > 1:
        raise DdeError(
            "POLICY_DENIED",
            "integration.merge_queue.concurrency must be 1 per project",
            retryable=False,
            details={"concurrency": flags.merge_queue_concurrency},
        )
    if flags.routing_exploration_epsilon > 0 and flags.autonomy_default_ceiling >= 5:
        raise DdeError(
            "POLICY_DENIED",
            "routing.exploration.epsilon > 0 is forbidden with "
            "autonomy.default_ceiling >= 5",
            retryable=False,
        )
