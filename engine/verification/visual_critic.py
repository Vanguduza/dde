"""DDE-068 visual-critic policy and versioned rubric loading.

The multimodal model supplies bounded dimension scores/findings. DDE, not the
model, computes the weighted aggregate and pass threshold from the committed
rubric artifact. This keeps the subjective evidence reproducible while
preventing a provider from silently redefining what PASS means.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from engine.capabilities.visual_critic import (
    VisualCriticDimensionResult,
    VisualCriticRubricItem,
)
from engine.core.errors import DdeError

RUBRIC_PATH = (
    Path(__file__).resolve().parents[2]
    / "schemas"
    / "design"
    / "visual_critic_rubric.v1.json"
)
DEFAULT_VISUAL_CRITIC_MODEL = "z-ai/glm-5.3-flash"
PER_CYCLE_COST_CEILING_USD = 0.05
MONTHLY_PROJECT_COST_CEILING_USD = 10.0
MAX_CRITIQUE_CYCLES = 3


@dataclass(frozen=True)
class LoadedVisualCriticRubric:
    version: str
    content_hash: str
    pass_threshold: float
    items: tuple[VisualCriticRubricItem, ...]


def load_visual_critic_rubric(
    path: Path = RUBRIC_PATH,
) -> LoadedVisualCriticRubric:
    try:
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DdeError(
            "POLICY_DENIED",
            "visual critic rubric could not be loaded",
            retryable=False,
            details={"path": str(path)},
        ) from exc
    if not isinstance(data, dict):
        raise DdeError(
            "POLICY_DENIED",
            "visual critic rubric must be a JSON object",
            retryable=False,
        )
    version = data.get("rubric_version")
    score_scale = data.get("score_scale")
    dimensions = data.get("dimensions")
    if (
        not isinstance(version, str)
        or not version
        or not isinstance(score_scale, dict)
        or not isinstance(dimensions, list)
        or not dimensions
    ):
        raise DdeError(
            "POLICY_DENIED",
            "visual critic rubric is missing required version/scale/dimensions",
            retryable=False,
        )
    threshold = score_scale.get("pass_threshold")
    if not isinstance(threshold, int | float) or isinstance(threshold, bool):
        raise DdeError(
            "POLICY_DENIED",
            "visual critic pass_threshold must be numeric",
            retryable=False,
        )
    items: list[VisualCriticRubricItem] = []
    seen: set[str] = set()
    for row in dimensions:
        if not isinstance(row, dict):
            raise DdeError("POLICY_DENIED", "visual critic dimension must be an object")
        rubric_id = row.get("rubric_id")
        title = row.get("title")
        instruction = row.get("instruction")
        weight = row.get("weight")
        if (
            not isinstance(rubric_id, str)
            or not rubric_id
            or rubric_id in seen
            or not isinstance(title, str)
            or not title
            or not isinstance(instruction, str)
            or not instruction
            or not isinstance(weight, int | float)
            or isinstance(weight, bool)
            or float(weight) <= 0
        ):
            raise DdeError(
                "POLICY_DENIED",
                "visual critic rubric contains an invalid dimension",
                retryable=False,
                details={"rubric_id": str(rubric_id)},
            )
        seen.add(rubric_id)
        items.append(
            VisualCriticRubricItem(
                rubric_id=rubric_id,
                title=title,
                instruction=instruction,
                weight=float(weight),
            )
        )
    return LoadedVisualCriticRubric(
        version=version,
        content_hash=hashlib.sha256(raw).hexdigest(),
        pass_threshold=float(threshold),
        items=tuple(items),
    )


def weighted_score(
    rubric: LoadedVisualCriticRubric,
    dimensions: tuple[VisualCriticDimensionResult, ...],
) -> float:
    scores = {item.rubric_id: item.score for item in dimensions}
    expected = {item.rubric_id for item in rubric.items}
    if set(scores) != expected:
        raise DdeError(
            "POLICY_DENIED",
            "visual critic result does not contain the exact rubric dimensions",
            retryable=False,
        )
    numerator = sum(item.weight * scores[item.rubric_id] for item in rubric.items)
    denominator = sum(item.weight for item in rubric.items)
    return numerator / denominator
