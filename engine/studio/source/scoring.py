"""Evidence-backed candidate scoring. Hard failures dominate numeric fit."""

from __future__ import annotations

from dataclasses import dataclass

REQUIRED_DIMENSIONS = (
    "product_fit",
    "feature_coverage",
    "design_system_fit",
    "responsive_fit",
    "accessibility_fit",
    "architecture_fit",
    "dependency_posture",
    "security_posture",
    "license_confidence",
    "provenance_confidence",
)


@dataclass(frozen=True)
class ScoreDecision:
    score_state: str
    overall_score: float | None
    classification: str
    dimensions: dict[str, object]
    hard_failures: tuple[str, ...]
    evidence_refs: tuple[str, ...]


def score_candidate(
    dimensions: dict[str, dict[str, object]], *, hard_failures: tuple[str, ...] = ()
) -> ScoreDecision:
    evidence_refs: list[str] = []
    normalized: dict[str, object] = {}
    missing: list[str] = []
    values: list[float] = []
    for name in REQUIRED_DIMENSIONS:
        row = dimensions.get(name)
        if not isinstance(row, dict):
            missing.append(name)
            continue
        value = row.get("score")
        refs = row.get("evidence_refs")
        if not isinstance(value, (int, float)) or not 0 <= float(value) <= 100:
            missing.append(name)
            continue
        if (
            not isinstance(refs, list)
            or not refs
            or not all(isinstance(v, str) and v for v in refs)
        ):
            missing.append(name)
            continue
        normalized[name] = {"score": float(value), "evidence_refs": list(refs)}
        values.append(float(value))
        evidence_refs.extend(refs)

    if hard_failures:
        return ScoreDecision(
            "BLOCKED",
            None,
            "BLOCKED",
            {**normalized, "missing_dimensions": missing},
            tuple(dict.fromkeys(hard_failures)),
            tuple(dict.fromkeys(evidence_refs)),
        )
    if missing:
        return ScoreDecision(
            "UNSCORED",
            None,
            "UNSCORED",
            {**normalized, "missing_dimensions": missing},
            (),
            tuple(dict.fromkeys(evidence_refs)),
        )
    overall = round(sum(values) / len(values), 2)
    classification = "GOOD" if overall >= 80 else ("MEDIUM" if overall >= 60 else "LOW")
    return ScoreDecision(
        "SCORED",
        overall,
        classification,
        normalized,
        (),
        tuple(dict.fromkeys(evidence_refs)),
    )
