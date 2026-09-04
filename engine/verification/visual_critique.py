"""DDE-068 multimodal visual critique: rubric, structured verdict schema,
fail-closed parsing and the deterministic pass/fail policy the promotion
gate actually consumes (EDR-0016 policy, executed via EDR-0017 Option C's
narrow `capability.visual_critique`).

**The gate never reads prose.** The model returns one schema-validated JSON
object; `parse_verdict` validates it and `evaluate_verdict` applies the
playbook's own numeric rule ("any dimension <4 blocks merge", section 8).
The model's own `verdict` word is recorded but is *not* the authority: if
it claims PASS while a scored dimension is below the blocking threshold,
the deterministic policy blocks. A model cannot talk its way past the gate.

**Malformed output fails closed**, never silently passes: every parse
failure raises a typed `DdeError`, which `run_check` surfaces as `ERRORED`
(Chapter 11.1's "a check that could not run proves nothing, in either
direction") -- distinct from a genuine visual `FAILED`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from engine.core.errors import DdeError

#: Versioned rubric (EDR-0016 decision 3: rubric text lives under
#: `schemas/design/` alongside `tokens.json`, under the Ch.3.1 drift-gate
#: discipline, so verdicts are reproducible against named inputs).
RUBRIC_PATH: Final = (
    Path(__file__).resolve().parents[2]
    / "schemas"
    / "design"
    / "visual_critique_rubric.json"
)

#: Playbook section 8: "Each dimension scored 1-5; any dimension <4 blocks
#: merge." Transcribed, not chosen here.
SCORE_MINIMUM: Final = 1
SCORE_MAXIMUM: Final = 5
BLOCKING_THRESHOLD: Final = 4

#: EDR-0016 decision 5 / charter: "bounded revise <=3 cycles; cycle count >3
#: blocks auto-progression and requires explicit human approval."
MAX_REVISION_CYCLES: Final = 3

DIMENSION_KEYS: Final[tuple[str, ...]] = (
    "pattern_fidelity",
    "token_discipline",
    "hierarchy_and_rhythm",
    "data_presentation",
    "copy_voice",
    "states_completeness",
    "motion_restraint",
    "accessibility",
    "believable_density",
)

_DEFECT_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {
        "dimension": {"type": "string", "enum": list(DIMENSION_KEYS)},
        "detail": {"type": "string"},
    },
    "required": ["dimension", "detail"],
    "additionalProperties": False,
}

#: Handed to the critic runtime so the response is schema-constrained at
#: source, AND re-validated here on the way back. Belt and braces: a runtime
#: that ignores the schema still cannot get a malformed verdict past
#: `parse_verdict`.
VERDICT_JSON_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["PASS", "BLOCK"]},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "dimension_scores": {
            "type": "object",
            "properties": {
                key: {
                    "type": "integer",
                    "minimum": SCORE_MINIMUM,
                    "maximum": SCORE_MAXIMUM,
                }
                for key in DIMENSION_KEYS
            },
            "required": list(DIMENSION_KEYS),
            "additionalProperties": False,
        },
        "blocking_defects": {"type": "array", "items": _DEFECT_SCHEMA},
        "non_blocking_defects": {"type": "array", "items": _DEFECT_SCHEMA},
        "repair_instructions": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": [
        "verdict",
        "confidence",
        "dimension_scores",
        "blocking_defects",
        "non_blocking_defects",
        "repair_instructions",
        "summary",
    ],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class VisualDefect:
    dimension: str
    detail: str


@dataclass(frozen=True)
class VisualCritiqueVerdict:
    """The validated structured critique. `rubric_version`, `model` and
    `cost_usd` are attached by the caller from the adapter's own transport
    metadata -- never read from the model's response, so a model cannot
    spoof which rubric it was judged against or what it cost."""

    verdict: str
    confidence: float
    dimension_scores: dict[str, int]
    blocking_defects: tuple[VisualDefect, ...]
    non_blocking_defects: tuple[VisualDefect, ...]
    repair_instructions: tuple[str, ...]
    summary: str
    rubric_version: str
    model: str | None = None
    cost_usd: float | None = None


def load_rubric() -> dict[str, Any]:
    try:
        raw: Any = json.loads(RUBRIC_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DdeError(
            "POLICY_DENIED",
            "visual critique rubric is missing or unreadable",
            details={"path": str(RUBRIC_PATH), "error": str(exc)},
        ) from exc
    if not isinstance(raw, dict):
        raise DdeError(
            "POLICY_DENIED",
            "visual critique rubric must be a JSON object",
            details={"path": str(RUBRIC_PATH)},
        )
    return raw


def _defects(raw: Any, *, field: str) -> tuple[VisualDefect, ...]:
    if not isinstance(raw, list):
        raise DdeError(
            "VALIDATION_FAILED",
            f"critique {field} must be an array",
            details={"field": field},
        )
    defects: list[VisualDefect] = []
    for item in raw:
        if not isinstance(item, dict):
            raise DdeError(
                "VALIDATION_FAILED",
                f"critique {field} entries must be objects",
                details={"field": field},
            )
        dimension = item.get("dimension")
        detail = item.get("detail")
        if dimension not in DIMENSION_KEYS or not isinstance(detail, str):
            raise DdeError(
                "VALIDATION_FAILED",
                f"critique {field} entry is malformed",
                details={"field": field, "entry": str(item)[:200]},
            )
        defects.append(VisualDefect(dimension=dimension, detail=detail))
    return tuple(defects)


def parse_verdict(
    raw_json: str,
    *,
    rubric_version: str,
    model: str | None = None,
    cost_usd: float | None = None,
) -> VisualCritiqueVerdict:
    """Validate a critic response. Any deviation from
    `VERDICT_JSON_SCHEMA` raises -- there is no lenient path, no "best
    effort" salvage of prose, and no default-to-pass."""
    try:
        payload: Any = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise DdeError(
            "VALIDATION_FAILED",
            "visual critique response is not valid JSON",
            details={"error": str(exc), "head": raw_json[:200]},
        ) from exc
    if not isinstance(payload, dict):
        raise DdeError(
            "VALIDATION_FAILED",
            "visual critique response must be a JSON object",
            details={"head": raw_json[:200]},
        )

    # `VERDICT_JSON_SCHEMA` declares additionalProperties: false, so enforce
    # it here too: an unknown key means the response did not come from the
    # contract we asked for. It also stops a model asserting fields it has
    # no authority over (`rubric_version`, `cost_usd`, `model`), which the
    # caller attaches from real transport metadata instead.
    unknown = sorted(set(payload) - set(VERDICT_JSON_SCHEMA["properties"]))
    if unknown:
        raise DdeError(
            "VALIDATION_FAILED",
            "visual critique response carries unknown fields",
            details={"unknown": ",".join(unknown)[:200]},
        )

    verdict = payload.get("verdict")
    if verdict not in {"PASS", "BLOCK"}:
        raise DdeError(
            "VALIDATION_FAILED",
            "critique verdict must be 'PASS' or 'BLOCK'",
            details={"verdict": str(verdict)[:80]},
        )

    confidence = payload.get("confidence")
    if not isinstance(confidence, int | float) or isinstance(confidence, bool):
        raise DdeError(
            "VALIDATION_FAILED",
            "critique confidence must be a number",
            details={"confidence": str(confidence)[:80]},
        )
    if not 0.0 <= float(confidence) <= 1.0:
        raise DdeError(
            "VALIDATION_FAILED",
            "critique confidence must be within [0, 1]",
            details={"confidence": float(confidence)},
        )

    raw_scores = payload.get("dimension_scores")
    if not isinstance(raw_scores, dict):
        raise DdeError(
            "VALIDATION_FAILED",
            "critique dimension_scores must be an object",
            details={},
        )
    scores: dict[str, int] = {}
    for key in DIMENSION_KEYS:
        value = raw_scores.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            raise DdeError(
                "VALIDATION_FAILED",
                f"critique dimension_scores.{key} must be an integer",
                details={"dimension": key, "value": str(value)[:80]},
            )
        if not SCORE_MINIMUM <= value <= SCORE_MAXIMUM:
            raise DdeError(
                "VALIDATION_FAILED",
                f"critique dimension_scores.{key} out of range",
                details={"dimension": key, "value": value},
            )
        scores[key] = value

    repair_raw = payload.get("repair_instructions")
    if not isinstance(repair_raw, list) or not all(
        isinstance(item, str) for item in repair_raw
    ):
        raise DdeError(
            "VALIDATION_FAILED",
            "critique repair_instructions must be an array of strings",
            details={},
        )
    summary = payload.get("summary")
    if not isinstance(summary, str):
        raise DdeError(
            "VALIDATION_FAILED", "critique summary must be a string", details={}
        )

    return VisualCritiqueVerdict(
        verdict=verdict,
        confidence=float(confidence),
        dimension_scores=scores,
        blocking_defects=_defects(
            payload.get("blocking_defects"), field="blocking_defects"
        ),
        non_blocking_defects=_defects(
            payload.get("non_blocking_defects"), field="non_blocking_defects"
        ),
        repair_instructions=tuple(repair_raw),
        summary=summary,
        rubric_version=rubric_version,
        model=model,
        cost_usd=cost_usd,
    )


@dataclass(frozen=True)
class CritiqueAssessment:
    passed: bool
    failing_dimensions: tuple[str, ...]
    detail: str


def evaluate_verdict(verdict: VisualCritiqueVerdict) -> CritiqueAssessment:
    """The deterministic policy the promotion gate consumes. Playbook
    section 8's own rule, applied to validated fields -- not the model's
    `verdict` word, which is advisory and cannot override a sub-threshold
    score."""
    failing = tuple(
        key
        for key in DIMENSION_KEYS
        if verdict.dimension_scores[key] < BLOCKING_THRESHOLD
    )
    blocking = verdict.blocking_defects
    passed = not failing and not blocking and verdict.verdict == "PASS"
    if failing:
        detail = (
            f"dimensions below the blocking threshold ({BLOCKING_THRESHOLD}): "
            + ", ".join(f"{key}={verdict.dimension_scores[key]}" for key in failing)
        )
    elif blocking:
        detail = "blocking defects: " + "; ".join(
            f"{item.dimension}: {item.detail}" for item in blocking
        )
    elif verdict.verdict != "PASS":
        detail = "critic returned BLOCK with no dimension below threshold"
    else:
        detail = "all rubric dimensions at or above the blocking threshold"
    return CritiqueAssessment(passed=passed, failing_dimensions=failing, detail=detail)


@dataclass(frozen=True)
class RevisionDecision:
    action: str
    cycle: int
    detail: str


def decide_revision_action(
    *,
    assessment: CritiqueAssessment,
    completed_cycles: int,
    max_cycles: int = MAX_REVISION_CYCLES,
) -> RevisionDecision:
    """Bounded repair policy (EDR-0016 decision 5). `completed_cycles` is
    how many critique cycles this candidate has already consumed.

    - `PROMOTE`      -- the assessment passed; no further cycle.
    - `REVISE`       -- blocked, and budget remains: the caller may apply
                        `repair_instructions`, re-render and critique again.
    - `ESCALATE_HUMAN` -- blocked and the bound is spent. Auto-progression
                        stops here; a human decides. Never silently
                        promotes, and never grants a fourth cycle.

    This function is the whole bound: it is pure, so the cap cannot be
    bypassed by a caller losing count -- the caller must pass the real
    cycle count, and any value at or past `max_cycles` refuses another.
    """
    if completed_cycles < 0:
        raise DdeError(
            "VALIDATION_FAILED",
            "completed_cycles cannot be negative",
            details={"completed_cycles": completed_cycles},
        )
    if assessment.passed:
        return RevisionDecision(
            action="PROMOTE",
            cycle=completed_cycles,
            detail="critique passed; candidate is eligible for promotion",
        )
    if completed_cycles >= max_cycles:
        return RevisionDecision(
            action="ESCALATE_HUMAN",
            cycle=completed_cycles,
            detail=(
                f"revision bound of {max_cycles} cycles is exhausted and the "
                f"candidate still blocks ({assessment.detail}); "
                "auto-progression stops and a human must decide"
            ),
        )
    return RevisionDecision(
        action="REVISE",
        cycle=completed_cycles + 1,
        detail=(f"cycle {completed_cycles + 1} of {max_cycles}: {assessment.detail}"),
    )
