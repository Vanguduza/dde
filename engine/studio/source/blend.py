"""Target source-blend preference validation.

Target weights describe a *future* generation preference. They never rewrite
actual provenance, which is derived only from accepted attribution records.
"""

from __future__ import annotations

from engine.core.errors import DdeError


def normalize_target_blend(
    weights: dict[str, float], *, known_provider_keys: frozenset[str]
) -> dict[str, float]:
    if not weights:
        raise DdeError("VALIDATION_FAILED", "target source blend requires weights")
    unknown = sorted(set(weights) - known_provider_keys)
    if unknown:
        raise DdeError(
            "VALIDATION_FAILED",
            "target source blend names unknown providers",
            details={"unknown_provider_keys": unknown},
        )
    normalized = {key: float(value) for key, value in sorted(weights.items())}
    if any(value < 0 or value > 1 for value in normalized.values()):
        raise DdeError(
            "VALIDATION_FAILED",
            "target source blend weights must be between 0 and 1",
        )
    total = sum(normalized.values())
    if abs(total - 1.0) > 1e-6:
        raise DdeError(
            "VALIDATION_FAILED",
            "target source blend weights must sum to 1.0",
            details={"sum": total},
        )
    return normalized
