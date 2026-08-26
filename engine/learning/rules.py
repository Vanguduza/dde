"""Chapter 6.8 learning eligibility -- pure, over already-computed
production signals.

An `ExperienceRecord` is eligible for routing training only when all
hold (Chapter 6.8):

1. `experience_origin = real` (never simulation).
2. `verification_confidence` is above threshold.
3. `failure_attribution` is `route_attributable` or `none`. Failures
   attributed to context, environment, tool, specification or upstream
   dependency are excluded, or included with a down-weight only when
   attribution confidence is low and the record is flagged.
4. The outcome is terminal -- no in-flight or superseded attempts.

The Chapter 6.5 flaky-check amendment is applied as a fifth filter: a
check quarantined from routing-learning eligibility cannot teach the
router.

DDE-034's `FailureAttribution.outcome` is a three-way
(context / not_context / inconclusive). This module maps that onto
Chapter 6.8's vocabulary without fabricating environment/tool/
specification/upstream classes no writer produces (EDR-0032).
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from engine.core.hashing import sha256_hex
from engine.learning.model import (
    ATTRIBUTION_DOWN_WEIGHTED,
    ATTRIBUTION_EXCLUDED_PREFIX,
    CONFIDENCE_REASON,
    DEFAULT_VERIFICATION_CONFIDENCE_THRESHOLD,
    ELIGIBLE_ATTRIBUTIONS,
    EXCLUDED_ATTRIBUTIONS,
    FLAKY_QUARANTINE_REASON,
    HOLDOUT_FRACTION_BYTE,
    LOW_ATTRIBUTION_CONFIDENCE_THRESHOLD,
    NOT_TERMINAL_REASON,
    SIMULATION_ORIGIN_REASON,
    EligibilityVerdict,
)

FailureAttributionClass = Literal[
    "none",
    "route_attributable",
    "context",
    "environment",
    "tool",
    "specification",
    "upstream",
    "inconclusive",
]


def map_failure_attribution(
    *,
    actual_verified_outcome: Literal["PASSED", "FAILED"] | None,
    attribution_outcome: str | None,
    attribution_confidence: float | None,
) -> tuple[FailureAttributionClass, float]:
    """Map DDE-034's three-way outcome onto Chapter 6.8 vocabulary.

    PASSED (no failure) is `none`. FAILED + `not_context_attributed` is
    `route_attributable`. FAILED + `context_attributed` is `context`.
    FAILED + `inconclusive` (or missing attribution) is `inconclusive`.
    Environment/tool/specification/upstream are reserved enum values;
    no writer in this codebase produces them.
    """
    if actual_verified_outcome == "PASSED" or attribution_outcome is None:
        if actual_verified_outcome == "PASSED":
            return "none", 1.0
        return "inconclusive", (
            attribution_confidence if attribution_confidence is not None else 0.0
        )
    if attribution_outcome == "not_context_attributed":
        return "route_attributable", (
            attribution_confidence if attribution_confidence is not None else 1.0
        )
    if attribution_outcome == "context_attributed":
        return "context", (
            attribution_confidence if attribution_confidence is not None else 1.0
        )
    return "inconclusive", (
        attribution_confidence if attribution_confidence is not None else 0.0
    )


def holdout_partition(experience_id: UUID) -> Literal["train", "holdout"]:
    """Deterministic train/holdout split. Hashed so UUID7 timestamps
    cannot cluster a day's records into one partition."""
    digest = sha256_hex(str(experience_id))
    return "holdout" if int(digest[:2], 16) < HOLDOUT_FRACTION_BYTE else "train"


def evaluate_eligibility(
    *,
    experience_origin: Literal["real", "simulation"],
    verification_confidence: float,
    failure_attribution: FailureAttributionClass,
    attribution_confidence: float,
    terminal: bool,
    flaky_quarantined: bool,
    verification_confidence_threshold: float = (
        DEFAULT_VERIFICATION_CONFIDENCE_THRESHOLD
    ),
) -> EligibilityVerdict:
    """Chapter 6.8 four-condition filter plus the Chapter 6.5 flaky
    quarantine. Every condition that fired is named in `reasons` so a
    reader of one row never has to cross-reference this module."""
    reasons: list[str] = []
    eligible = True
    down_weighted = False

    if experience_origin != "real":
        eligible = False
        reasons.append(SIMULATION_ORIGIN_REASON)

    if verification_confidence < verification_confidence_threshold:
        eligible = False
        reasons.append(CONFIDENCE_REASON)

    if failure_attribution not in ELIGIBLE_ATTRIBUTIONS:
        if (
            failure_attribution in EXCLUDED_ATTRIBUTIONS
            and attribution_confidence < LOW_ATTRIBUTION_CONFIDENCE_THRESHOLD
        ):
            down_weighted = True
            reasons.append(ATTRIBUTION_DOWN_WEIGHTED)
        else:
            eligible = False
            reasons.append(ATTRIBUTION_EXCLUDED_PREFIX + failure_attribution)

    if not terminal:
        eligible = False
        reasons.append(NOT_TERMINAL_REASON)

    if flaky_quarantined:
        eligible = False
        reasons.append(FLAKY_QUARANTINE_REASON)

    if eligible and not reasons:
        reasons.append("eligible")

    return EligibilityVerdict(
        eligible_for_routing_training=eligible,
        down_weighted=down_weighted,
        reasons=tuple(reasons),
        failure_attribution=failure_attribution,
        attribution_confidence=attribution_confidence,
    )
