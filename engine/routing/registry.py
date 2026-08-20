"""Minimal, in-code worker-profile registry — an explicitly flagged
Stage 1 stand-in for Chapter 8's certified-profile registry (DDE-011,
"WorkerAdapter + Worker Manager + first certified profile"), not that
registry itself.

Chapter 6.2's policy example names five profile IDs
(`profile.longcontext_economy`, `profile.general_implementation`,
`profile.premium_reasoning`, `profile.deterministic_runner`,
`profile.vision`) without describing their capability/environment
declarations — that detail belongs to Chapter 8's `WorkerProfile` object,
which does not exist yet. This module declares only the minimum a Stage 1
router needs to evaluate Chapter 6.1's capability (gate 1) and environment
(gate 4) hard gates against those same five named profiles: which
capabilities each supports and which environment classes it can run in.
It is a constant, not a persisted table — Chapter 3.8 does not assign a
`worker_profiles` table to any Stage 1 mission, and the brief for this
mission forbids building that registry early.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.routing.policy import (
    CAPABILITY_BROWSER,
    CAPABILITY_REPOSITORY,
    CAPABILITY_TESTING,
    MODALITY_IMAGE,
    PROFILE_DETERMINISTIC_RUNNER,
    PROFILE_GENERAL_IMPLEMENTATION,
    PROFILE_LONGCONTEXT_ECONOMY,
    PROFILE_PREMIUM_REASONING,
    PROFILE_VISION,
)

ENVIRONMENT_STANDARD = "container-standard"
ENVIRONMENT_BROWSER = "container-browser"


@dataclass(frozen=True)
class WorkerProfile:
    profile_id: str
    capabilities: frozenset[str]
    environment_classes: frozenset[str]


PROFILES: dict[str, WorkerProfile] = {
    PROFILE_LONGCONTEXT_ECONOMY: WorkerProfile(
        profile_id=PROFILE_LONGCONTEXT_ECONOMY,
        capabilities=frozenset({CAPABILITY_REPOSITORY, CAPABILITY_TESTING}),
        environment_classes=frozenset({ENVIRONMENT_STANDARD}),
    ),
    PROFILE_GENERAL_IMPLEMENTATION: WorkerProfile(
        profile_id=PROFILE_GENERAL_IMPLEMENTATION,
        capabilities=frozenset({CAPABILITY_REPOSITORY, CAPABILITY_TESTING}),
        environment_classes=frozenset({ENVIRONMENT_STANDARD}),
    ),
    PROFILE_PREMIUM_REASONING: WorkerProfile(
        profile_id=PROFILE_PREMIUM_REASONING,
        capabilities=frozenset({CAPABILITY_REPOSITORY, CAPABILITY_TESTING}),
        environment_classes=frozenset({ENVIRONMENT_STANDARD}),
    ),
    PROFILE_DETERMINISTIC_RUNNER: WorkerProfile(
        profile_id=PROFILE_DETERMINISTIC_RUNNER,
        capabilities=frozenset({CAPABILITY_REPOSITORY, CAPABILITY_TESTING}),
        environment_classes=frozenset({ENVIRONMENT_STANDARD}),
    ),
    PROFILE_VISION: WorkerProfile(
        profile_id=PROFILE_VISION,
        capabilities=frozenset(
            {
                CAPABILITY_REPOSITORY,
                CAPABILITY_TESTING,
                CAPABILITY_BROWSER,
                MODALITY_IMAGE,
            }
        ),
        environment_classes=frozenset({ENVIRONMENT_STANDARD, ENVIRONMENT_BROWSER}),
    ),
}


def required_environment_class(required_capabilities: tuple[str, ...]) -> str:
    """Chapter 6.1 gate 4 input. No ExecutionEnvironment registry exists yet
    (Chapter 7, DDE-010): the only real signal available today is whether
    the workload's own declared capability requirement names the browser,
    so that is the entire Stage 1 derivation."""
    if CAPABILITY_BROWSER in required_capabilities:
        return ENVIRONMENT_BROWSER
    return ENVIRONMENT_STANDARD
