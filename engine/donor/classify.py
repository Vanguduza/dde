"""Chapter 13.8 six-value source_class placeholder (DDE-046).

Full licence/reuse classification is DDE-047. Until then ingest defaults to
UNKNOWN and refuses a silent OPEN_REUSE upgrade without a signed reuse
decision id (the `donor_reuse` approval path).
"""

from __future__ import annotations

from uuid import UUID

from engine.core.errors import DdeError

SOURCE_CLASSES = frozenset(
    {
        "OPEN_REUSE",
        "CONDITIONAL_REUSE",
        "SOURCE_REFERENCE_ONLY",
        "RESTRICTED",
        "UNKNOWN",
        "REJECTED",
    }
)

DEFAULT_SOURCE_CLASS = "UNKNOWN"


def resolve_source_class(
    requested: str | None,
    *,
    signed_reuse_decision_id: UUID | None,
) -> str:
    """Return the class to persist; never silently promote to OPEN_REUSE."""
    if requested is None or requested == "":
        return DEFAULT_SOURCE_CLASS
    if requested not in SOURCE_CLASSES:
        raise DdeError(
            "POLICY_DENIED",
            f"Unknown donor source_class {requested!r}",
            details={"source_class": requested},
        )
    if requested == "OPEN_REUSE" and signed_reuse_decision_id is None:
        raise DdeError(
            "POLICY_DENIED",
            "OPEN_REUSE requires a signed reuse decision (donor_reuse); "
            "refusing silent upgrade from UNKNOWN (Chapter 13.8 / DDE-046)",
            details={
                "requested": requested,
                "default": DEFAULT_SOURCE_CLASS,
            },
        )
    return requested
