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

# Appendix A harness classes — vendor names isolated here, never in Ch.2–20.
HARNESS_HERMES = "harness.hermes"
HARNESS_DEEPSEEK = "harness.deepseek"

# Credential tier for Hermes/DeepSeek OpenRouter-backed models (project-owner
# requirement; see docs/truth/edr/EDR-0001-subscription-based-worker-credentials.md).
OPENROUTER_CREDENTIAL_PROVIDER = "deepseek_api_key"


@dataclass(frozen=True)
class WorkerProfile:
    profile_id: str
    capabilities: frozenset[str]
    environment_classes: frozenset[str]
    harness_class: str | None = None


@dataclass(frozen=True)
class OpenRouterModelSpec:
    """Declared free-tier OpenRouter model entry for Hermes/DeepSeek harnesses."""

    model_id: str
    strengths: frozenset[str]
    harness_classes: frozenset[str]


@dataclass(frozen=True)
class OpenRouterModelSelection:
    model_id: str
    credential_provider: str
    reason_codes: tuple[str, ...]


# Top free OpenRouter models, verified live against
# https://openrouter.ai/api/v1/models on 2026-08-22 (18 `:free` endpoints that
# day). The catalog rotates weekly — providers delist `:free` endpoints without
# notice — so entries carry declared strength vectors used by
# `resolve_openrouter_model` to match workload classes, and an override can pin
# a specific model per call. Replaced by measured telemetry once DDE-035's
# actual-cost gap closes. Ordered strongest-first per harness fit.
OPENROUTER_FREE_MODELS: tuple[OpenRouterModelSpec, ...] = (
    # 1M-context frontier reasoning/orchestration MoE; top-used free model.
    OpenRouterModelSpec(
        model_id="nvidia/nemotron-3-ultra-550b-a55b:free",
        strengths=frozenset({"reasoning", "architecture", "debugging", "long_context"}),
        harness_classes=frozenset({HARNESS_DEEPSEEK, HARNESS_HERMES}),
    ),
    # Purpose-built coding-agent model (Terminal-Bench 2.1 70.2%).
    OpenRouterModelSpec(
        model_id="poolside/laguna-s-2.1:free",
        strengths=frozenset({"implementation", "batch"}),
        harness_classes=frozenset({HARNESS_DEEPSEEK, HARNESS_HERMES}),
    ),
    # Large-scale reasoning; long-horizon agent workflows, project-level SE.
    OpenRouterModelSpec(
        model_id="z-ai/glm-5.2:free",
        strengths=frozenset({"reasoning", "architecture", "long_context"}),
        harness_classes=frozenset({HARNESS_DEEPSEEK}),
    ),
    # Cohere's agentic coding model; trained across agent harnesses.
    OpenRouterModelSpec(
        model_id="cohere/north-mini-code:free",
        strengths=frozenset({"implementation", "debugging"}),
        harness_classes=frozenset({HARNESS_HERMES}),
    ),
    # Compact coding-agent tier; cheap batch implementation work.
    OpenRouterModelSpec(
        model_id="poolside/laguna-xs-2.1:free",
        strengths=frozenset({"implementation", "batch", "general"}),
        harness_classes=frozenset({HARNESS_HERMES, HARNESS_DEEPSEEK}),
    ),
    # High-throughput general MoE for multi-agent orchestration.
    OpenRouterModelSpec(
        model_id="nvidia/nemotron-3-super-120b-a12b:free",
        strengths=frozenset({"orchestration", "delegation", "general"}),
        harness_classes=frozenset({HARNESS_HERMES}),
    ),
    # Multimodal instruct fallback; native function calling.
    OpenRouterModelSpec(
        model_id="google/gemma-4-31b-it:free",
        strengths=frozenset({"general", "batch"}),
        harness_classes=frozenset({HARNESS_HERMES, HARNESS_DEEPSEEK}),
    ),
)

WORKLOAD_STRENGTHS: dict[str, tuple[str, ...]] = {
    "architectural_reasoning": ("reasoning", "architecture", "debugging"),
    "bulk_implementation": ("implementation", "batch", "corpus"),
    "verification": (),
    "visual_analysis": ("general",),
}

PROFILE_HARNESS_CLASS: dict[str, str] = {
    PROFILE_LONGCONTEXT_ECONOMY: HARNESS_DEEPSEEK,
    PROFILE_GENERAL_IMPLEMENTATION: HARNESS_HERMES,
    PROFILE_PREMIUM_REASONING: HARNESS_DEEPSEEK,
}

#: Mirrors `engine.governance.config.OPENROUTER_MODES` without importing it
#: (governance stays dependency-minimal). Kept in sync by tests.
MODEL_SELECTION_MODES = ("off", "auto", "fixed")


def resolve_model_selection(
    mode: str, fixed_model_id: str | None
) -> tuple[bool, str | None]:
    """Translate an operator's model-selection mode into the
    `(enable_openrouter_models, openrouter_model_override)` pair
    `engine.routing.rules.evaluate` consumes.

    - "off" disables resolution entirely;
    - "auto" enables strength-matched selection per task;
    - "fixed" pins `fixed_model_id`, which must name a declared catalog
      entry (any harness class — a pinned id that cannot serve the selected
      profile's harness class resolves to no model downstream, disclosed
      via reason codes rather than silently substituted).
    """
    if mode == "off":
        return (False, None)
    if mode == "auto":
        return (True, None)
    if mode == "fixed":
        if fixed_model_id is None:
            raise ValueError("mode='fixed' requires a fixed_model_id")
        if not any(spec.model_id == fixed_model_id for spec in OPENROUTER_FREE_MODELS):
            raise ValueError(
                f"fixed_model_id {fixed_model_id!r} is not in the declared "
                "OpenRouter catalog"
            )
        return (True, fixed_model_id)
    raise ValueError(f"unknown model-selection mode: {mode!r}")


def resolve_openrouter_model(
    *,
    profile_id: str,
    workload_class: str,
    model_override: str | None = None,
) -> OpenRouterModelSelection | None:
    """Select a declared OpenRouter free model for Appendix A harness profiles.

    Deterministic: walks the declared catalog in order, picks the first model
    whose harness class matches and whose strengths overlap the workload's
    declared strength vector. `model_override` wins when it names a catalog
    entry for the profile's harness class.
    """
    harness_class = PROFILE_HARNESS_CLASS.get(profile_id)
    if harness_class is None:
        return None

    eligible = tuple(
        spec for spec in OPENROUTER_FREE_MODELS if harness_class in spec.harness_classes
    )
    if not eligible:
        return None

    if model_override is not None:
        override_spec = next(
            (spec for spec in eligible if spec.model_id == model_override), None
        )
        if override_spec is None:
            return None
        return OpenRouterModelSelection(
            model_id=override_spec.model_id,
            credential_provider=OPENROUTER_CREDENTIAL_PROVIDER,
            reason_codes=("OPENROUTER_OVERRIDE",),
        )

    desired = WORKLOAD_STRENGTHS.get(workload_class, ("general",))
    best: OpenRouterModelSpec | None = None
    best_score = -1
    for spec in eligible:
        score = sum(1 for strength in desired if strength in spec.strengths)
        if score > best_score:
            best_score = score
            best = spec
    if best is None:
        best = eligible[0]
    return OpenRouterModelSelection(
        model_id=best.model_id,
        credential_provider=OPENROUTER_CREDENTIAL_PROVIDER,
        reason_codes=(f"OPENROUTER_STRENGTH_MATCH:{best_score}",),
    )


PROFILES: dict[str, WorkerProfile] = {
    PROFILE_LONGCONTEXT_ECONOMY: WorkerProfile(
        profile_id=PROFILE_LONGCONTEXT_ECONOMY,
        capabilities=frozenset({CAPABILITY_REPOSITORY, CAPABILITY_TESTING}),
        environment_classes=frozenset({ENVIRONMENT_STANDARD}),
        harness_class=HARNESS_DEEPSEEK,
    ),
    PROFILE_GENERAL_IMPLEMENTATION: WorkerProfile(
        profile_id=PROFILE_GENERAL_IMPLEMENTATION,
        capabilities=frozenset({CAPABILITY_REPOSITORY, CAPABILITY_TESTING}),
        environment_classes=frozenset({ENVIRONMENT_STANDARD}),
        harness_class=HARNESS_HERMES,
    ),
    PROFILE_PREMIUM_REASONING: WorkerProfile(
        profile_id=PROFILE_PREMIUM_REASONING,
        capabilities=frozenset({CAPABILITY_REPOSITORY, CAPABILITY_TESTING}),
        environment_classes=frozenset({ENVIRONMENT_STANDARD}),
        harness_class=HARNESS_DEEPSEEK,
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
