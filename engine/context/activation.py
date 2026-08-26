"""Chapter 5.13 context-policy activation gates and mode machine -- pure.

`context.mode` progresses `certified_baseline -> shadow -> canary ->
promoted`. ROLLBACK is reachable from any state and returns to the last
certified policy, never an untested arm.

Candidate arms are first-class (Graft Pattern 5 / DDE-059): `pull` (Stage
1 certified), `push` (unevictable architecture bundle injected up front),
`semantic` (Stage 3 retriever). Canary and promoted require a promotion
run whose `deferred_gates` is empty -- PARTIAL_PASS is a refusal, never
a flip of `ContextService.compile()`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from engine.core.hashing import sha256_hex

ContextMode = Literal["certified_baseline", "shadow", "canary", "promoted"]
ContextArm = Literal["pull", "push", "semantic"]

MODE_ORDER: tuple[ContextMode, ...] = (
    "certified_baseline",
    "shadow",
    "canary",
    "promoted",
)

PROMOTABLE_MODES: tuple[ContextMode, ...] = ("shadow", "canary", "promoted")
CERTIFIED_ARMS: tuple[ContextArm, ...] = ("pull", "push", "semantic")

DEFAULT_CANARY_FRACTION = 0.05

DEFERRED_REPLAY_GATES = (
    "context_attributed_failure_rate",
    "task_success_on_corpus",
)


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    mandatory: bool
    observed: float | int | None
    required: float | int | None
    reason: str


@dataclass(frozen=True)
class ActivationVerdict:
    """Whether a requested context-mode advance is permitted."""

    allowed: bool
    requested_mode: ContextMode
    current_mode: ContextMode
    gates: tuple[GateResult, ...]
    refused_reasons: tuple[str, ...]


@dataclass(frozen=True)
class CompilePolicy:
    """What `ContextService.compile()` should apply for one task."""

    semantic_enabled: bool
    assembly_arm: Literal["pull", "push"]
    source: str


def compile_policy_from_activation(
    *,
    mode: ContextMode | None,
    candidate_arm: ContextArm,
    canary_fraction: float,
    task_id: UUID,
) -> CompilePolicy:
    """Certified baseline and shadow always serve Stage 1 pull. Canary
    applies the candidate arm only on the hash-stable slice; promoted
    applies it to every compile. Semantic uses pull assembly plus the
    semantic retriever."""
    if mode is None or mode in ("certified_baseline", "shadow"):
        source = mode if mode is not None else "certified_baseline"
        return CompilePolicy(False, "pull", source)
    apply = mode == "promoted" or (
        mode == "canary" and in_canary_slice(task_id, canary_fraction)
    )
    if not apply:
        return CompilePolicy(False, "pull", "canary_control")
    if candidate_arm == "semantic":
        return CompilePolicy(True, "pull", mode)
    if candidate_arm == "push":
        return CompilePolicy(False, "push", mode)
    return CompilePolicy(False, "pull", mode)


def last_certified_mode(
    *,
    current: ContextMode,
    certified: ContextMode | None,
) -> ContextMode:
    """ROLLBACK returns to the last certified policy, never an untested
    arm. Uncertified current modes fall back to certified_baseline."""
    del current
    if certified in MODE_ORDER:
        return certified
    return "certified_baseline"


def can_transition(*, current: ContextMode, target: ContextMode) -> bool:
    """Forward one step. Skipping (certified_baseline -> canary) is
    refused. Same-mode is a no-op."""
    if target == current:
        return True
    try:
        here = MODE_ORDER.index(current)
        there = MODE_ORDER.index(target)
    except ValueError:
        return False
    return there == here + 1


def in_canary_slice(task_id: UUID, fraction: float) -> bool:
    """Hash-stable limited-canary assignment. Fraction 0 never assigns;
    1 always does. Does not select an arm -- only whether this task is
    in the candidate slice."""
    if fraction <= 0:
        return False
    if fraction >= 1:
        return True
    bucket = int(sha256_hex(str(task_id))[:8], 16) % 10_000
    return bucket < int(fraction * 10_000)


def evaluate_activation_gates(
    *,
    current_mode: ContextMode,
    requested_mode: ContextMode,
    candidate_arm: ContextArm,
    promotion_decision: str | None,
    deferred_gates: tuple[str, ...] | None,
    implemented_gate_fail: bool = False,
) -> ActivationVerdict:
    """Refuse canary/promoted when Chapter 5.13 'all must hold' is not
    evidenced. `insufficient_evidence` is a refusal, never a silent
    pass. Shadow is observation-only and does not require a full
    promotion run."""
    refused: list[str] = []
    gates: list[GateResult] = []

    if requested_mode not in PROMOTABLE_MODES:
        return ActivationVerdict(
            allowed=False,
            requested_mode=requested_mode,
            current_mode=current_mode,
            gates=(),
            refused_reasons=("requested_mode_not_promotable",),
        )
    if candidate_arm not in CERTIFIED_ARMS:
        return ActivationVerdict(
            allowed=False,
            requested_mode=requested_mode,
            current_mode=current_mode,
            gates=(),
            refused_reasons=("unknown_candidate_arm",),
        )
    if not can_transition(current=current_mode, target=requested_mode):
        return ActivationVerdict(
            allowed=False,
            requested_mode=requested_mode,
            current_mode=current_mode,
            gates=(),
            refused_reasons=("illegal_mode_transition",),
        )

    if requested_mode == "shadow":
        gates.append(
            GateResult(
                name="shadow_observation_only",
                passed=True,
                mandatory=True,
                observed=1,
                required=1,
                reason="ok",
            )
        )
        return ActivationVerdict(
            allowed=True,
            requested_mode=requested_mode,
            current_mode=current_mode,
            gates=tuple(gates),
            refused_reasons=(),
        )

    # canary / promoted: Chapter 5.13 all-must-hold
    if promotion_decision == "INSUFFICIENT_CORPUS":
        gates.append(_bool_gate("corpus_adequate", False, insufficient=False))
        refused.append("insufficient_corpus")
    elif promotion_decision == "FAIL" or implemented_gate_fail:
        gates.append(_bool_gate("implemented_gates_hold", False, insufficient=False))
        refused.append("promotion_gate_fail")
    elif promotion_decision is None:
        gates.append(_bool_gate("promotion_run_recorded", False, insufficient=True))
        refused.append("promotion_run_recorded_insufficient_evidence")
    else:
        gates.append(_bool_gate("promotion_run_recorded", True, insufficient=False))
        gates.append(
            _bool_gate(
                "implemented_gates_hold",
                promotion_decision != "FAIL",
                insufficient=False,
            )
        )

    remaining = tuple(deferred_gates or ())
    replay_missing = tuple(name for name in DEFERRED_REPLAY_GATES if name in remaining)
    gates.append(
        GateResult(
            name="chapter_5_13_all_gates_computed",
            passed=not remaining,
            mandatory=True,
            observed=len(remaining),
            required=0,
            reason=(
                "ok"
                if not remaining
                else "chapter_5_13_gates_incomplete:" + ",".join(remaining)
            ),
        )
    )
    if remaining:
        refused.append(gates[-1].reason)
    if replay_missing:
        gates.append(
            GateResult(
                name="worker_verification_replay",
                passed=False,
                mandatory=True,
                observed=None,
                required=None,
                reason="worker_verification_replay_insufficient_evidence",
            )
        )

    # PARTIAL_PASS is never sufficient to flip production compile()
    if promotion_decision == "PARTIAL_PASS_IMPLEMENTED_GATES_ONLY":
        refused.append("partial_pass_does_not_flip_production")

    # Deduplicate while preserving order
    unique: list[str] = []
    for reason in refused:
        if reason not in unique:
            unique.append(reason)

    return ActivationVerdict(
        allowed=not unique,
        requested_mode=requested_mode,
        current_mode=current_mode,
        gates=tuple(gates),
        refused_reasons=tuple(unique),
    )


def _bool_gate(
    name: str,
    passed: bool,
    *,
    insufficient: bool,
    mandatory: bool = True,
) -> GateResult:
    if insufficient:
        return GateResult(
            name=name,
            passed=False,
            mandatory=mandatory,
            observed=None,
            required=None,
            reason=f"{name}_insufficient_evidence",
        )
    return GateResult(
        name=name,
        passed=passed,
        mandatory=mandatory,
        observed=1 if passed else 0,
        required=1,
        reason="ok" if passed else f"{name}_unmet",
    )
