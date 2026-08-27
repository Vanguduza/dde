"""First-party catalogs consumed by the generation-prompt compiler."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "schemas" / "design"

PLAYBOOK_VERSION = "1.2"


@lru_cache(maxsize=1)
def _load(name: str) -> dict[str, Any]:
    payload = json.loads((DESIGN / name).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{name} must be a JSON object")
    return payload


def nevers_catalog() -> dict[str, Any]:
    return _load("nevers.json")


def copy_law_catalog() -> dict[str, Any]:
    return _load("copy_law.json")


def layout_patterns_catalog() -> dict[str, Any]:
    return _load("layout_patterns.json")


def font_pairings_catalog() -> dict[str, Any]:
    return _load("font_pairings.json")


NEVER_ITEMS: tuple[dict[str, str], ...] = tuple(
    {"id": str(item["id"]), "statement": str(item["statement"])}
    for item in nevers_catalog()["items"]
)
COPY_FORBIDDEN_PHRASES: tuple[str, ...] = tuple(
    str(phrase) for phrase in copy_law_catalog()["forbidden_phrases"]
)
COPY_RULES: tuple[str, ...] = tuple(str(rule) for rule in copy_law_catalog()["rules"])
LAYOUT_PATTERN_IDS: frozenset[str] = frozenset(
    str(item["id"]) for item in layout_patterns_catalog()["patterns"]
)
LAYOUT_PATTERNS: tuple[dict[str, str], ...] = tuple(
    {"id": str(item["id"]), "description": str(item["description"])}
    for item in layout_patterns_catalog()["patterns"]
)
