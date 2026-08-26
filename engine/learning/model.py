"""In-process value objects for the Chapter 6.8 ExperienceRecord engine
(DDE-057).

`schemas/objects/experience_record.json` is the durable contract this
module owns (Chapter 3.8); `EligibilityVerdict` is the pure filter output
before identity and promotion state are stamped on the persisted row.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

#: Chapter 6.8: "verification_confidence is above threshold -- a failure
#: detected by a flaky or low-confidence verifier does not teach the
#: router anything." Raise-able configuration, not product truth; 0.9
#: matches Chapter 6.9's verification-backed coverage default.
DEFAULT_VERIFICATION_CONFIDENCE_THRESHOLD = 0.9

#: Chapter 6.8: excluded attributions "included with a down-weight only
#: when attribution confidence is low and the record is flagged."
LOW_ATTRIBUTION_CONFIDENCE_THRESHOLD = 0.5

#: ~20% holdout, hashed so UUID7 timestamps cannot cluster partitions.
HOLDOUT_FRACTION_BYTE = 51  # 51/256 ≈ 0.199

ELIGIBLE_ATTRIBUTIONS = frozenset({"route_attributable", "none"})
EXCLUDED_ATTRIBUTIONS = frozenset(
    {
        "context",
        "environment",
        "tool",
        "specification",
        "upstream",
        "inconclusive",
    }
)

SIMULATION_ORIGIN_REASON = "experience_origin=simulation: excluded by construction"
CONFIDENCE_REASON = "verification_confidence_below_threshold"
ATTRIBUTION_EXCLUDED_PREFIX = "attribution_excluded:"
ATTRIBUTION_DOWN_WEIGHTED = "attribution_down_weighted_low_confidence"
NOT_TERMINAL_REASON = "outcome_not_terminal"
FLAKY_QUARANTINE_REASON = "flaky_check_quarantined_from_routing_learning"
SUPERSEDED_REASON = "attempt_superseded"


@dataclass(frozen=True)
class EligibilityVerdict:
    """One deterministic Chapter 6.8 eligibility computation."""

    eligible_for_routing_training: bool
    down_weighted: bool
    reasons: tuple[str, ...]
    failure_attribution: Literal[
        "none",
        "route_attributable",
        "context",
        "environment",
        "tool",
        "specification",
        "upstream",
        "inconclusive",
    ]
    attribution_confidence: float
