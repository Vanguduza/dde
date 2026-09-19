"""EDR-0019 Epic F postcondition completion gating.

`ExternalEffect.status` answers whether the request was sent and reconciled.
It does not answer whether the world changed. A task that depends on an external
mutation may not be reported complete while a required postcondition is still
pending, verifying, unverifiable or refuted -- "the API returned 200" is not
"the desired state exists".
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.core.errors import DdeError

NOT_REQUIRED = "NOT_REQUIRED"
REQUIRED = "REQUIRED"
REQUIRED_INDEPENDENT = "REQUIRED_INDEPENDENT"

REQUIRED_PENDING = "REQUIRED_PENDING"
VERIFYING = "VERIFYING"
VERIFIED = "VERIFIED"
PARTIAL = "PARTIAL"
UNVERIFIABLE = "UNVERIFIABLE"
REFUTED = "REFUTED"

#: Postcondition states that block a dependent task from reaching COMPLETED.
BLOCKING_STATES = frozenset(
    {REQUIRED_PENDING, VERIFYING, UNVERIFIABLE, REFUTED, PARTIAL}
)

#: Effect classes whose postcondition must be observed independently of the
#: adapter that performed the effect.
HIGH_IMPACT_EFFECT_CLASSES = frozenset({"EXTERNAL_NON_IDEMPOTENT", "IRREVERSIBLE"})


@dataclass(frozen=True, slots=True)
class EffectPostcondition:
    effect_id: str
    side_effect_class: str
    postcondition_policy: str
    postcondition_state: str | None


@dataclass(frozen=True, slots=True)
class VerificationObservation:
    verifier_type: str
    outcome: str
    independent_of_adapter: bool


def required_policy_for(side_effect_class: str) -> str:
    """High-impact effects need an independent observation; reads need none."""
    if side_effect_class in HIGH_IMPACT_EFFECT_CLASSES:
        return REQUIRED_INDEPENDENT
    if side_effect_class == "EXTERNAL_IDEMPOTENT":
        return REQUIRED
    return NOT_REQUIRED


def resolve_state(
    *, policy: str, observations: tuple[VerificationObservation, ...]
) -> str:
    """Fold observations into a postcondition state.

    Engine-reported success contributes nothing here: only an observation can
    produce VERIFIED, and under REQUIRED_INDEPENDENT it must be an observation
    the acting adapter did not produce.
    """
    if policy == NOT_REQUIRED:
        return NOT_REQUIRED
    if not observations:
        return REQUIRED_PENDING
    usable = [
        observation
        for observation in observations
        if policy != REQUIRED_INDEPENDENT or observation.independent_of_adapter
    ]
    if not usable:
        # Observations exist but none is independent, so the requirement stands.
        return VERIFYING
    if any(observation.outcome == "REFUTED" for observation in usable):
        return REFUTED
    if any(observation.outcome == "SUCCESS" for observation in usable):
        return VERIFIED
    if any(observation.outcome == "PARTIAL" for observation in usable):
        return PARTIAL
    if any(observation.outcome == "UNVERIFIABLE" for observation in usable):
        return UNVERIFIABLE
    return VERIFYING


def blocking_effects(
    effects: tuple[EffectPostcondition, ...],
) -> tuple[EffectPostcondition, ...]:
    return tuple(
        effect
        for effect in effects
        if effect.postcondition_policy != NOT_REQUIRED
        and (effect.postcondition_state or REQUIRED_PENDING) in BLOCKING_STATES
    )


def require_completable(effects: tuple[EffectPostcondition, ...]) -> None:
    """Refuse task completion while any required postcondition is unproven."""
    blocking = blocking_effects(effects)
    if not blocking:
        return
    raise DdeError(
        "EVIDENCE_MISSING",
        "task cannot complete while a required external postcondition is unproven",
        retryable=False,
        details={
            "effects": [
                {
                    "effect_id": effect.effect_id,
                    "postcondition_state": effect.postcondition_state
                    or REQUIRED_PENDING,
                }
                for effect in blocking
            ]
        },
    )
