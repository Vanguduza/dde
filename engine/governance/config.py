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
    #: Provider-agnostic model selection for Appendix A harness profiles:
    #: "off" (no resolution), "auto" (router strength-matches per task),
    #: "fixed" (pin `model_fixed_id` served by `model_fixed_provider`).
    #: Model choice only reorders candidates downstream of every hard gate,
    #: so it is legal in all environment classes; every value is validated
    #: everywhere anyway because a typo must fail closed rather than
    #: silently mean "off". Selection records declared metadata on the
    #: RouteDecision only — adapters make no live provider call until the
    #: broker wires credentials (EDR-0001 Path B).
    model_mode: str = "off"
    model_fixed_id: str | None = None
    model_fixed_provider: str | None = None
    #: Chapter 13.7 `android.offline_queue.enabled`. Default false — edge
    #: clients (Termux/Android) arm their durable offline queue only when
    #: this flag (or the DDE_ANDROID_OFFLINE_QUEUE_ENABLED env twin) is true.
    #: Not a dangerous startup combination; named here so the flag is a
    #: first-class configuration surface rather than an ad-hoc env string.
    android_offline_queue_enabled: bool = False


MODEL_MODES = ("off", "auto", "fixed")

#: Mirrors the provider ids of `engine.routing.registry.MODEL_PROVIDERS`.
#: Governance must not import engine.routing, so the ids are restated here;
#: tests/unit/test_routing_adoption_features.py asserts the two stay aligned.
MODEL_PROVIDERS = ("openrouter", "deepseek", "anthropic")


def validate_configuration(flags: RuntimeFlags) -> None:
    """Chapter 13.7: a dangerous combination must be impossible to reach
    by editing a value. Raises POLICY_DENIED; does not coerce.

    The model-mode checks run for every environment class: they are
    enum/consistency hygiene, not environment-dependent danger — a model
    selection never changes a hard-gate outcome, only which declared
    model/provider a surviving harness profile would be annotated with."""
    if flags.model_mode not in MODEL_MODES:
        raise DdeError(
            "POLICY_DENIED",
            f"routing.model.mode must be one of {MODEL_MODES}",
            retryable=False,
            details={"model_mode": flags.model_mode},
        )
    if flags.model_mode == "fixed" and (
        not flags.model_fixed_id or not flags.model_fixed_provider
    ):
        raise DdeError(
            "POLICY_DENIED",
            "routing.model.mode=fixed requires both routing.model.fixed_id "
            "and routing.model.fixed_provider",
            retryable=False,
        )
    if flags.model_fixed_provider is not None and (
        flags.model_fixed_provider not in MODEL_PROVIDERS
    ):
        raise DdeError(
            "POLICY_DENIED",
            f"routing.model.fixed_provider must be one of {MODEL_PROVIDERS}",
            retryable=False,
            details={"model_fixed_provider": flags.model_fixed_provider},
        )
    if flags.model_mode != "fixed" and (
        flags.model_fixed_id is not None or flags.model_fixed_provider is not None
    ):
        # "off" must stay off; "auto" means the router chooses, so any pin
        # attached to either mode is a contradiction, not an override.
        raise DdeError(
            "POLICY_DENIED",
            "routing.model.fixed_id/fixed_provider are contradictory with "
            f"mode={flags.model_mode!r} (only mode=fixed may pin)",
            retryable=False,
            details={"model_mode": flags.model_mode},
        )
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
