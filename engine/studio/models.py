"""Internal value objects for generation-prompt compilation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RequirementInput:
    requirement_id: str
    slug: str
    statement: str
    status: str


@dataclass(frozen=True)
class FeatureSurface:
    feature_id: str
    title: str
    purpose: str
    layout_pattern: str
    states: tuple[str, ...]


@dataclass(frozen=True)
class CompileRequest:
    prd_id: str
    prd_version: str
    playbook_version: str
    tokens_version: int
    tokens_hash: str
    art_direction: dict[str, Any] | None
    requirements: tuple[RequirementInput, ...]
    features: tuple[FeatureSurface, ...]


@dataclass(frozen=True)
class GenerationPrompt:
    prd_id: str
    prd_version: str
    playbook_version: str
    tokens_version: int
    tokens_hash: str
    art_direction_id: str
    art_direction_version: str
    prompt_body: str
    content_hash: str
    preview_html: str
    provenance: dict[str, object]
