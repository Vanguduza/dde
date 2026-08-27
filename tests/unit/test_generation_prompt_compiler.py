"""Unit pins for DDE-065 fail-closed art-direction and token resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.studio.art_direction import validate_art_direction
from engine.studio.catalog import LAYOUT_PATTERN_IDS, NEVER_ITEMS, PLAYBOOK_VERSION
from engine.studio.errors import CompileRefusedError
from engine.studio.tokens_pin import resolve_tokens_pin, tokens_file_hash

_ROLES = frozenset(
    {
        "surfaceBase",
        "surfaceCard",
        "textPrimary",
        "accentPrimary",
        "statusOk",
        "statusWarn",
        "statusErr",
    }
)

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "schemas" / "design"


def _art() -> dict[str, object]:
    return {
        "record_id": "ad-1",
        "product_id": "p1",
        "version": "1",
        "design_read": "Settings form for operators; English; token foundation.",
        "dials": {
            "DESIGN_VARIANCE": 3,
            "MOTION_INTENSITY": 2,
            "VISUAL_DENSITY": 5,
        },
        "type_pairing": {
            "pairing_id": "source-serif-sans",
            "display": "Source Serif 4",
            "body": "Source Sans 3",
        },
        "palette_roles": {
            "canvas": "surfaceBase",
            "surface": "surfaceCard",
            "ink": "textPrimary",
            "accent": "accentPrimary",
            "semantic_ok": "statusOk",
            "semantic_warn": "statusWarn",
            "semantic_err": "statusErr",
        },
        "theme_atmosphere": "Restrained.",
        "typography_hierarchy": "Serif display, sans body.",
        "component_stylings": [{"component": "field", "states": ["idle", "error"]}],
        "layout_idiom": "settings form",
        "layout_principles": "One pattern.",
        "depth_elevation": "overlay token only",
        "dos_donts": {"dos": ["tokens"], "donts": ["hex"]},
        "responsive_behavior": "stack at 960px",
        "agent_prompt_guide": "Stay on tokens.",
        "motion_identity": "restrained",
    }


def test_playbook_version_constant() -> None:
    assert PLAYBOOK_VERSION == "1.2"


def test_never_catalog_covers_section_1_1() -> None:
    ids = {item["id"] for item in NEVER_ITEMS}
    assert "NEVER-GRADIENT-PRIMARY" in ids
    assert "NEVER-PURPLE-INDIGO" in ids
    assert len(NEVER_ITEMS) == 11


def test_layout_patterns_include_playbook_set() -> None:
    assert "dashboard-ov-grid" in LAYOUT_PATTERN_IDS
    assert "mission-control-columnar" in LAYOUT_PATTERN_IDS
    assert "settings-form" in LAYOUT_PATTERN_IDS


def test_tokens_pin_resolves_current_sheet() -> None:
    sheet = resolve_tokens_pin(version=1, content_hash=tokens_file_hash())
    assert sheet.version == 1
    assert "surfaceBase" in sheet.semantic_role_names


def test_tokens_pin_refuses_wrong_hash() -> None:
    with pytest.raises(CompileRefusedError) as captured:
        resolve_tokens_pin(version=1, content_hash="a" * 64)
    assert captured.value.details is not None
    assert captured.value.details["missing_artifact"] == "tokens"


def test_art_direction_accepts_explicit_inter() -> None:
    art = _art()
    art["type_pairing"] = {
        "pairing_id": "inter-explicit",
        "display": "Inter",
        "body": "Inter",
        "explicit_inter_display": True,
    }
    validate_art_direction(art, semantic_role_names=_ROLES)


def test_art_direction_refuses_unknown_pairing() -> None:
    art = _art()
    art["type_pairing"] = {
        "pairing_id": "comic-sans-stack",
        "display": "Comic Sans MS",
        "body": "Arial",
    }
    with pytest.raises(CompileRefusedError):
        validate_art_direction(art, semantic_role_names=_ROLES)


def test_font_corpus_bans_inter_as_default() -> None:
    corpus = json.loads((DESIGN / "font_pairings.json").read_text(encoding="utf-8"))
    assert corpus["ban_inter_as_default_display"] is True
    inter = next(p for p in corpus["pairings"] if p["id"] == "inter-explicit")
    assert inter["requires_explicit_inter_display"] is True
