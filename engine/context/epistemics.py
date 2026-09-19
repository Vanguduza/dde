"""EDR-0019 Epic H epistemic context facts.

A model must never receive "the project uses X" when the underlying record says
"X may be useful". Authority class is carried through compilation, conflicts are
resolved by rank rather than recency, and inference is never silently promoted
to fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType

from engine.core.errors import DdeError

AUTHORITY_ORDER: tuple[str, ...] = (
    "OWNER_CANONICAL",
    "PROJECT_TRUTH",
    "POLICY_CANONICAL",
    "VERIFIED_LIVE_STATE",
    "VERIFIED_REPOSITORY_STATE",
    "VERIFIED_HISTORY",
    "QUALIFIED_KNOWLEDGE",
    "LEARNED_CANDIDATE",
    "MODEL_INFERENCE",
    "UNTRUSTED_EXTERNAL",
)
_RANK = MappingProxyType({name: index for index, name in enumerate(AUTHORITY_ORDER)})

#: Classes that can never satisfy a requirement declared canonical.
NON_CANONICAL = frozenset(
    {
        "QUALIFIED_KNOWLEDGE",
        "LEARNED_CANDIDATE",
        "MODEL_INFERENCE",
        "UNTRUSTED_EXTERNAL",
    }
)
#: Classes that must be rendered with their label attached, never as plain fact.
MUST_LABEL = frozenset({"LEARNED_CANDIDATE", "MODEL_INFERENCE", "UNTRUSTED_EXTERNAL"})
#: Classes no compilation step may promote without an explicit promotion record.
NEVER_AUTO_PROMOTE = frozenset({"MODEL_INFERENCE", "UNTRUSTED_EXTERNAL"})

_TRUTH_CLASSES = frozenset({"OWNER_CANONICAL", "PROJECT_TRUTH", "POLICY_CANONICAL"})


@dataclass(frozen=True, slots=True)
class Fact:
    fact_id: str
    subject: str
    predicate: str
    authority_class: str
    observed_at: datetime
    valid_until: datetime | None = None
    superseded_by_fact_id: str | None = None


def rank(authority_class: str) -> int:
    try:
        return _RANK[authority_class]
    except KeyError as exc:
        raise DdeError(
            "VALIDATION_FAILED",
            f"unknown authority class {authority_class}",
            retryable=False,
        ) from exc


def outranks(left: str, right: str) -> bool:
    return rank(left) < rank(right)


def is_valid(fact: Fact, *, now: datetime | None = None) -> bool:
    if fact.superseded_by_fact_id is not None:
        return False
    if fact.valid_until is None:
        return True
    return (now or datetime.now(UTC)) < fact.valid_until


def resolve(facts: tuple[Fact, ...], *, now: datetime | None = None) -> Fact | None:
    """Pick the governing fact for one subject/predicate.

    Rank decides first and recency only breaks ties inside a rank, so a fresh
    model inference can never displace Project Truth.
    """
    live = [fact for fact in facts if is_valid(fact, now=now)]
    if not live:
        return None
    return sorted(
        live,
        key=lambda fact: (rank(fact.authority_class), -fact.observed_at.timestamp()),
    )[0]


def may_supersede(incumbent: Fact, challenger: Fact) -> bool:
    """VERIFIED_LIVE_STATE may refresh a stale observation, never rewrite truth."""
    if incumbent.authority_class in _TRUTH_CLASSES:
        return challenger.authority_class in _TRUTH_CLASSES
    return rank(challenger.authority_class) <= rank(incumbent.authority_class)


def require_can_satisfy_canonical(fact: Fact) -> None:
    if fact.authority_class in NON_CANONICAL:
        raise DdeError(
            "POLICY_DENIED",
            f"{fact.authority_class} cannot satisfy a canonical requirement",
            retryable=False,
            details={"fact_id": fact.fact_id, "subject": fact.subject},
        )


def render_for_model(fact: Fact, statement: str) -> str:
    """Compile a fact for model context with its authority label preserved."""
    if fact.authority_class in MUST_LABEL:
        return f"{fact.authority_class}: {statement}"
    return statement


def require_promotable(fact: Fact, *, promoted_by_ref: str | None) -> None:
    if fact.authority_class in NEVER_AUTO_PROMOTE and not promoted_by_ref:
        raise DdeError(
            "POLICY_DENIED",
            f"{fact.authority_class} may not be persisted as fact without "
            "an explicit promotion record",
            retryable=False,
            details={"fact_id": fact.fact_id},
        )
