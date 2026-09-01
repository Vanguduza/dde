"""Chapter 13.1–13.4 governance constants.

Enumerations are transcribed from the blueprint/accepted EDRs. DDE-068 adds
`prototype_pixel_signoff`: an explicit human waiver for the subjective VLM
visual threshold only. It is permanently ineligible for standing approval;
the Frontend Studio production call site mechanically proves all non-judge
checks passed before it can request this approval.
"""

from __future__ import annotations

from typing import Final

from engine.workers.budget import (
    ATTEMPT_MAX_TOKENS_KEY,
    ATTEMPT_MAX_TOOL_CALLS_KEY,
)

APPROVAL_TYPES: Final[frozenset[str]] = frozenset(
    {
        "architecture_change",
        "production_change",
        "scope_widening",
        "capability_grant",
        "oracle_approval",
        "irreversible_effect",
        "dependency_addition",
        "donor_reuse",
        "external_model_invocation",
        "budget_increase",
        "prototype_pixel_signoff",
    }
)

#: Chapter 13.2: standing authority can never pre-authorise these classes.
STANDING_FORBIDDEN_TYPES: Final[frozenset[str]] = frozenset(
    {
        "irreversible_effect",
        "production_change",
        "budget_increase",
        "external_model_invocation",
        # DDE-068: visual sign-off is meaningful only when a human inspects
        # the exact bound render/verification evidence. A standing waiver
        # would turn the critic into advisory-only behavior.
        "prototype_pixel_signoff",
    }
)

OPEN_APPROVAL_STATUSES: Final[frozenset[str]] = frozenset({"REQUESTED", "UNDER_REVIEW"})
USABLE_APPROVAL_STATUSES: Final[frozenset[str]] = frozenset({"APPROVED"})

BUDGET_REQUESTED_KIND: Final = "budget_requested"
BUDGET_MAX_TOKENS_KEY: Final = ATTEMPT_MAX_TOKENS_KEY
BUDGET_MAX_TOOL_CALLS_KEY: Final = ATTEMPT_MAX_TOOL_CALLS_KEY

RISK_ORDER: Final[dict[str, int]] = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}
BLAST_ORDER: Final[dict[str, int]] = {
    "local": 0,
    "module": 1,
    "cross_module": 2,
    "system": 3,
}

DEFAULT_REQUIRED_ROLE: Final = "approval.decide"
ATTENTION_SLA_HOURS: Final = 24
APPROVAL_TTL_HOURS: Final = 24
