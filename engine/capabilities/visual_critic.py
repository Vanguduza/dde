"""DDE-068 provider-neutral multimodal visual-critic capability.

The verification engine is allowed to ask for a subjective design judgement,
but it is not allowed to know which external API performs that judgement.
Provider request syntax, authentication and SDK/HTTP details live outside
this module. The result deliberately carries measured usage and cost so the
verification path can enforce EDR-0016's hard spending ceilings without
inventing estimates after the fact.

A VisualCriticCapability is advisory evidence only. It never edits a
workspace, mutates Project Truth, approves its own result, or overrides a
failed deterministic check.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class VisualCriticRubricItem:
    """One versioned rubric dimension supplied to the critic."""

    rubric_id: str
    title: str
    instruction: str
    weight: float


@dataclass(frozen=True)
class VisualCriticSpec:
    """One screenshot judgement request.

    `png_bytes` is captured from the real ProductEnvironment by
    `capability.browser`. `context` is bounded product/screen intent, not a
    hidden worker transcript. `model_id` is the policy-selected model pin;
    verification never asks an adapter to silently choose a different model.
    Tenant/project identity exists only so a broker-backed adapter can resolve
    the correct project-scoped credential without widening that credential.
    """

    tenant_id: UUID
    project_id: UUID
    png_bytes: bytes
    statement: str
    rubric_version: str
    rubric: tuple[VisualCriticRubricItem, ...]
    context: dict[str, str]
    model_id: str
    max_cost_usd: float


@dataclass(frozen=True)
class VisualCriticDimensionResult:
    rubric_id: str
    score: float
    finding: str


@dataclass(frozen=True)
class VisualCriticResult:
    """Structured result returned by a real multimodal provider adapter."""

    exit_code: int
    verdict: str
    score: float
    dimensions: tuple[VisualCriticDimensionResult, ...]
    findings: tuple[str, ...]
    model_id: str
    provider_id: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    duration_ms: int
    timed_out: bool
    stderr: str = ""


class VisualCriticCapability(Protocol):
    """Multimodal design-judgement seam used by verification."""

    async def critique(self, spec: VisualCriticSpec) -> VisualCriticResult: ...
