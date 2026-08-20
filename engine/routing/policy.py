"""Chapter 6.2 declared routing policy table ("v1 is deterministic and
explicit... a declared policy table, not a learned or simulated model").

This module is the in-code equivalent of the versioned, hash-pinned
`policies/routing/deterministic-v1.yaml` the chapter shows as an example.
No YAML/config-loading dependency exists in this project (Chapter 9.6), and
the example in 6.2 gives an exact literal table — `workload_classes` with
`prefer`/`require`/`forbid`/`min_risk`/`max_risk` per class, plus a global
`escalation` map — so it is reproduced here as a plain, versioned Python
constant rather than adding a YAML parser for a single, small, static file.

`POLICY_VERSION` is the literal filename stem from the chapter's example
(`deterministic-v1`), used as `RouteDecision.policy_version` (Chapter 6.3).

**Verification's `forbid` clause is a rule, not a static profile ID.** The
chapter's literal YAML reads `forbid: [profile.any_generator_of_the_change_
under_test]` — a templated placeholder for "whichever profile produced the
change under test", never a real, registrable profile identifier. Encoding
that string verbatim would be dead data (no candidate could ever match it).
`forbid_generator=True` instead names the actual rule (Chapter 6.2's
independence clause / Chapter 11.4 "a worker profile that produced a change
cannot execute the authoritative verification of that change") and is
enforced in `engine.routing.rules` against a caller-supplied
`previous_generator_profile_id`. No TaskAttempt/WorkerRun history exists yet
(Chapter 8/11, DDE-011/012) to source that automatically — Stage 1 callers
have no real value to pass, so it defaults to `None` (no exclusion), and the
rule itself is exercised directly in tests with a synthetic value. This is
flagged as a Stage 1 divergence: the mechanism is real, its automatic real
data source is not built yet.

`visual_analysis` is reproduced from the chapter's table for completeness
and is still evaluated against every registered profile (Chapter 6.3:
"`candidates[]` records **every** evaluated profile"), but Stage 1's
classifier (`engine.routing.rules.classify_workload`) never selects it: no
real per-task modality/visual signal exists yet (Chapter 5.2 lists the
Visual retriever as unbuilt until Stage 5+, DDE-044) and inventing a
keyword heuristic for it would be exactly the fabricated subsystem the
mission brief prohibits. It remains reachable only if a future caller with
a real modality signal supplies `workload_class` directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

POLICY_VERSION = "deterministic-v1"

CAPABILITY_REPOSITORY = "capability.repository"
CAPABILITY_TESTING = "capability.testing"
CAPABILITY_BROWSER = "capability.browser"
MODALITY_IMAGE = "modality.image"

PROFILE_LONGCONTEXT_ECONOMY = "profile.longcontext_economy"
PROFILE_GENERAL_IMPLEMENTATION = "profile.general_implementation"
PROFILE_PREMIUM_REASONING = "profile.premium_reasoning"
PROFILE_DETERMINISTIC_RUNNER = "profile.deterministic_runner"
PROFILE_VISION = "profile.vision"

HUMAN_DECISION_TASK = "human_decision_task"
NEXT_ELIGIBLE_BY_SCORE = "next_eligible_by_score"

RISK_LEVELS = ("low", "medium", "high", "critical")
RISK_ORDER = {level: index for index, level in enumerate(RISK_LEVELS)}


@dataclass(frozen=True)
class WorkloadPolicy:
    """One `workload_classes` entry from Chapter 6.2's declared table."""

    prefer: tuple[str, ...]
    require: tuple[str, ...] = ()
    forbid_generator: bool = False
    min_risk: str | None = None
    max_risk: str | None = None


WORKLOAD_CLASSES: dict[str, WorkloadPolicy] = {
    "bulk_implementation": WorkloadPolicy(
        prefer=(PROFILE_LONGCONTEXT_ECONOMY, PROFILE_GENERAL_IMPLEMENTATION),
        require=(CAPABILITY_REPOSITORY, CAPABILITY_TESTING),
        max_risk="medium",
    ),
    "architectural_reasoning": WorkloadPolicy(
        prefer=(PROFILE_PREMIUM_REASONING,),
        require=(CAPABILITY_REPOSITORY,),
        min_risk="high",
    ),
    "verification": WorkloadPolicy(
        prefer=(PROFILE_DETERMINISTIC_RUNNER,),
        forbid_generator=True,
    ),
    "visual_analysis": WorkloadPolicy(
        prefer=(PROFILE_VISION,),
        require=(CAPABILITY_BROWSER, MODALITY_IMAGE),
    ),
}


@dataclass(frozen=True)
class EscalationRule:
    trigger: str
    to: str
    condition: dict[str, object] = field(default_factory=dict)


# Chapter 6.1 gate 9 / 6.2's global `escalation` map. Declared, versioned
# policy — attached verbatim to every RouteDecision's `escalation_plan`
# (Chapter 3.10: a RouteDecision's definition is immutable and carries the
# policy in force at the time it was made), since none of these triggers
# (verification failure count, worker unavailability) are observable at
# routing-decision time in Stage 1 with no WorkerRun/verification history
# (Chapter 8/11, DDE-011/012) yet built.
ESCALATION_POLICY: tuple[EscalationRule, ...] = (
    EscalationRule(
        trigger="on_verification_failure",
        to=PROFILE_PREMIUM_REASONING,
        condition={"after": 2},
    ),
    EscalationRule(trigger="on_worker_unavailable", to=NEXT_ELIGIBLE_BY_SCORE),
    EscalationRule(trigger="on_ambiguity_high", to=HUMAN_DECISION_TASK),
)


def escalation_plan_json() -> list[dict[str, object]]:
    return [
        {"trigger": rule.trigger, "to": rule.to, "condition": dict(rule.condition)}
        for rule in ESCALATION_POLICY
    ]
