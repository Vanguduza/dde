"""Per-mission donor-search query ceiling (EDR-0015 / Ch.16.4).

Lives on `execution_plans.token_budget` under
`donor_search_max_queries`. Missing key uses the seeded default (32),
never unlimited. Exhaustion is `BudgetExhaustedError` — not an empty
inventory.
"""

from __future__ import annotations

from collections.abc import Mapping

from engine.core.errors import BudgetExhaustedError, DdeError

DONOR_SEARCH_MAX_QUERIES_KEY = "donor_search_max_queries"
DEFAULT_DONOR_SEARCH_MAX_QUERIES = 32


def resolve_donor_search_ceiling(token_budget: Mapping[str, object]) -> int:
    raw = token_budget.get(DONOR_SEARCH_MAX_QUERIES_KEY)
    if raw is None:
        return DEFAULT_DONOR_SEARCH_MAX_QUERIES
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        raise DdeError(
            "POLICY_DENIED",
            "donor_search_max_queries on the execution plan is not a "
            "non-negative integer",
            retryable=False,
            details={"quota_key": DONOR_SEARCH_MAX_QUERIES_KEY},
        )
    return raw


def assert_donor_search_quota(*, ceiling: int, requested: int, already: int) -> None:
    if requested < 0 or already < 0:
        raise DdeError(
            "POLICY_DENIED",
            "donor-search quota counters must be non-negative",
            retryable=False,
        )
    if requested + already > ceiling:
        raise BudgetExhaustedError(
            "donor-search query quota exhausted",
            details={
                "quota_key": DONOR_SEARCH_MAX_QUERIES_KEY,
                "ceiling": ceiling,
                "requested": requested,
                "already": already,
            },
        )
