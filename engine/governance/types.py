"""Chapter 13.1–13.4 constants. Enumerations are transcribed from the
chapter; they are not an invented vocabulary."""

from __future__ import annotations

from typing import Final

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
        # EDR-0001 Path A: invoking an external vendor's model on a human's
        # personal, rate-limited, ToS-bounded subscription seat (Claude Code
        # CLI). Distinct from `capability_grant` -- that class covers
        # DDE-mintable/brokerable capabilities; this one covers spend
        # against a human's own account that DDE cannot mint or revoke.
        "external_model_invocation",
    }
)

#: Chapter 13.2: standing authority can never pre-authorise these classes.
STANDING_FORBIDDEN_TYPES: Final[frozenset[str]] = frozenset(
    {
        "irreversible_effect",
        "production_change",
        # EDR-0001 Path A, human's explicit instruction: "a human manually
        # approve every piece of work routed to Claude Code" -- no
        # `StandingApproval` may ever pre-authorise a batch of Claude Code
        # invocations. This is a constraint on the approval class itself,
        # enforced by `ApprovalService.grant_standing`/`authorize_standing`
        # rejecting it outright; it must never be removed to make a
        # standing-approval caller's life easier.
        "external_model_invocation",
    }
)

OPEN_APPROVAL_STATUSES: Final[frozenset[str]] = frozenset({"REQUESTED", "UNDER_REVIEW"})
USABLE_APPROVAL_STATUSES: Final[frozenset[str]] = frozenset({"APPROVED"})

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
