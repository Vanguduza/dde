"""Attention candidate scoring, deduplication and budget enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

#: Classes that are never suppressed by a non-urgent budget or quiet hours.
BYPASS_CLASSES = frozenset({"SECURITY", "APPROVAL", "URGENT"})

_WEIGHTS: dict[str, float] = {
    "importance": 0.22,
    "urgency": 0.20,
    "actionability": 0.18,
    "blast_radius": 0.14,
    "time_sensitivity": 0.10,
    "novelty": 0.08,
    "confidence": 0.08,
}


@dataclass(frozen=True, slots=True)
class ScoreInputs:
    importance: float
    urgency: float
    actionability: float
    novelty: float
    confidence: float
    blast_radius: float
    time_sensitivity: float
    owner_required: bool = False
    repeat_penalty: float = 0.0


@dataclass(frozen=True, slots=True)
class AttentionBudget:
    max_nonurgent_per_hour: int
    max_nonurgent_per_day: int
    quiet_hours: tuple[tuple[int, int], ...] = ()
    repeat_cooldown_seconds: int = 3600


@dataclass(frozen=True, slots=True)
class BudgetUsage:
    emitted_last_hour: int
    emitted_last_day: int
    last_emitted_at: datetime | None = None


def score(inputs: ScoreInputs) -> float:
    """Weighted score in [0, 1]. Owner-required work is floored, not inflated."""
    raw = (
        _WEIGHTS["importance"] * inputs.importance
        + _WEIGHTS["urgency"] * inputs.urgency
        + _WEIGHTS["actionability"] * inputs.actionability
        + _WEIGHTS["blast_radius"] * inputs.blast_radius
        + _WEIGHTS["time_sensitivity"] * inputs.time_sensitivity
        + _WEIGHTS["novelty"] * inputs.novelty
        + _WEIGHTS["confidence"] * inputs.confidence
    )
    adjusted = max(0.0, raw - inputs.repeat_penalty)
    if inputs.owner_required:
        adjusted = max(adjusted, 0.5)
    return min(1.0, adjusted)


def dedupe_key(*parts: str) -> str:
    """Stable key so a repeating failure collapses into one attention item."""
    return ":".join(part.strip().lower().replace(" ", "_") for part in parts if part)


def repeat_penalty_for(repeat_count: int) -> float:
    """Each repeat costs score, bounded so a persistent blocker never vanishes."""
    if repeat_count <= 1:
        return 0.0
    return min(0.35, 0.08 * (repeat_count - 1))


def in_quiet_hours(moment: datetime, budget: AttentionBudget) -> bool:
    now = moment.astimezone(UTC).time()
    for start_hour, end_hour in budget.quiet_hours:
        start, end = time(start_hour), time(end_hour)
        if start <= end:
            if start <= now < end:
                return True
        elif now >= start or now < end:  # window wraps midnight
            return True
    return False


def disposition_for(
    *,
    attention_class: str,
    candidate_score: float,
    budget: AttentionBudget,
    usage: BudgetUsage,
    moment: datetime,
    is_duplicate: bool = False,
) -> tuple[str, bool]:
    """Return `(disposition, bypassed_budget)`.

    Security, approval and urgent classes bypass the non-urgent budget and quiet
    hours; nothing else does, and a duplicate never re-promotes.
    """
    if attention_class in BYPASS_CLASSES:
        return "PROMOTED", True
    if is_duplicate:
        return "SUPPRESSED_DUPLICATE", False
    if usage.last_emitted_at is not None:
        cooldown = timedelta(seconds=budget.repeat_cooldown_seconds)
        if moment - usage.last_emitted_at < cooldown:
            return "SUPPRESSED_DUPLICATE", False
    if in_quiet_hours(moment, budget):
        return "SUPPRESSED_QUIET_HOURS", False
    if usage.emitted_last_hour >= budget.max_nonurgent_per_hour:
        return "SUPPRESSED_BUDGET", False
    if usage.emitted_last_day >= budget.max_nonurgent_per_day:
        return "SUPPRESSED_BUDGET", False
    if candidate_score <= 0.0:
        return "SUPPRESSED_BUDGET", False
    return "PROMOTED", False
