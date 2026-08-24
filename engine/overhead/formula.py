"""Pure Chapter 16.4 overhead-budget arithmetic.

These functions are the formula, not a writer. Production mutation sites
call them and persist the result; tests pin the arithmetic without a
database.
"""

from __future__ import annotations

# Same Stage 1 approximation as `ContextItem.token_estimate` (Chapter 9.6:
# no tokenizer dependency).
CHARS_PER_TOKEN = 4

TOKEN_SHARE_ALERT = 0.25
TOKEN_SHARE_INVESTIGATE = 0.35
DEFAULT_HARD_CAP_TOKEN_SHARE = 0.40
OVERHEAD_SECONDS_S_P95_ALERT = 90.0
ENVIRONMENT_PROVISIONING_P95_ALERT_SECONDS = 45.0
CONTEXT_CRITIC_INVOCATION_SHARE_ALERT = 0.30
ROUTE_CRITIC_INVOCATION_SHARE_ALERT = 0.20


def estimate_tokens(text: str) -> int:
    """~4 characters per token. Empty text is 0, not 1."""
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN)


def planning_tokens_for(*, planning_mode: str, texts: tuple[str, ...]) -> int:
    """Model-assisted planning counts the produced textual artifacts.
    Template and human-authored graphs consume no model tokens."""
    if planning_mode != "model_assisted":
        return 0
    return estimate_tokens("\n".join(texts))


def overhead_tokens(
    *,
    context_assembly: int,
    context_critic: int,
    routing: int,
    route_critic: int,
    planning: int,
    judge: int,
) -> int:
    """Chapter 16.4 formula. Callers pass honest zeros for producers that
    do not yet exist (deterministic routing, unimplemented route critic,
    Stage 1 judge bindings)."""
    return context_assembly + context_critic + routing + route_critic + planning + judge


def token_share(overhead: int, mission_tokens: int) -> float | None:
    if mission_tokens <= 0:
        return None
    return overhead / float(mission_tokens)


def classify_token_share(
    share: float,
    *,
    alert: float = TOKEN_SHARE_ALERT,
    investigate: float = TOKEN_SHARE_INVESTIGATE,
    hard_cap: float = DEFAULT_HARD_CAP_TOKEN_SHARE,
) -> str | None:
    if share > hard_cap:
        return "hard_cap"
    if share > investigate:
        return "investigate"
    if share > alert:
        return "alert"
    return None


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = int(p * (len(ordered) - 1))
    return float(ordered[index])


def invocation_share(invoked: int, total: int) -> float | None:
    if total <= 0:
        return None
    return invoked / float(total)


def cost_per_verified_success(
    total_overhead_tokens: int, verified_success_count: int
) -> float | None:
    if verified_success_count <= 0:
        return None
    return total_overhead_tokens / float(verified_success_count)


def token_cost_regressed(
    baseline_mean: float | None, candidate_mean: float | None
) -> bool:
    """Chapter 16.4: a compile-token-cost regression blocks promotion.
    Empty denominator (no successful compiles) does not FAIL."""
    if baseline_mean is None or candidate_mean is None:
        return False
    return candidate_mean > baseline_mean


def mean(values: list[int]) -> float | None:
    if not values:
        return None
    return sum(values) / float(len(values))
