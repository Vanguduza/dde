"""DDE-065 generation-prompt compiler contract tests.

Charter: docs/planning/product-studio-charter.md (DDE-065). These tests
existed as failing pins before `engine.studio.compiler` was implemented.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

import pytest

from engine.studio.compiler import compile_generation_prompt
from engine.studio.errors import CompileRefusedError
from engine.studio.models import CompileRequest, FeatureSurface, RequirementInput
from engine.studio.tokens_pin import tokens_file_hash

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "schemas" / "design"
TOKENS_SCHEMA = DESIGN / "tokens.json"
PLAYBOOK = ROOT / "docs" / "planning" / "dde-frontend-ux-playbook.md"
STUDIO = ROOT / "engine" / "studio"

HEX_RE = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
RGB_RE = re.compile(r"rgba?\([^)]+\)")


def _palette_literals() -> set[str]:
    sheet = json.loads(TOKENS_SCHEMA.read_text(encoding="utf-8"))
    palette = sheet["properties"]["color"]["properties"]["palette"]["properties"]
    values = {item["const"] for item in palette.values()}
    values.add("#fff")
    values.add("#000")
    return values


def _valid_art_direction() -> dict[str, object]:
    return {
        "record_id": "ad-ledgerline-1",
        "product_id": "prd-ledgerline",
        "version": "1",
        "design_read": (
            "Operator worklist for finance clerks; dense English UI; "
            "token-sheet foundation."
        ),
        "dials": {
            "DESIGN_VARIANCE": 6,
            "MOTION_INTENSITY": 4,
            "VISUAL_DENSITY": 7,
        },
        "type_pairing": {
            "pairing_id": "ibm-plex",
            "display": "IBM Plex Serif",
            "body": "IBM Plex Sans",
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
        "theme_atmosphere": "Quiet industrial workshop, not a marketing site.",
        "typography_hierarchy": "Display serif for titles; sans for body and UI.",
        "component_stylings": [
            {
                "component": "primary-button",
                "states": ["idle", "loading", "disabled", "error"],
            }
        ],
        "layout_idiom": "columnar worklists with a trailing inspector.",
        "layout_principles": "One pattern per surface; no orphan layouts.",
        "depth_elevation": "Single overlay shadow token; no stacked glass.",
        "dos_donts": {
            "dos": ["Use token semantic aliases only."],
            "donts": ["Do not invent hex, px, or ms literals."],
        },
        "responsive_behavior": "Single column below 960px.",
        "agent_prompt_guide": "Stay inside the token sheet and nevers catalog.",
        "motion_identity": "measured",
    }


def _valid_request(**overrides: object) -> CompileRequest:
    req = CompileRequest(
        prd_id="prd-ledgerline",
        prd_version="1",
        playbook_version="1.2",
        tokens_version=1,
        tokens_hash=tokens_file_hash(),
        art_direction=_valid_art_direction(),
        requirements=(
            RequirementInput(
                requirement_id="req-1",
                slug="REQ-LL-001",
                statement="Clerks can post a balanced journal.",
                status="approved",
            ),
        ),
        features=(
            FeatureSurface(
                feature_id="feat-journals",
                title="Journal worklist",
                purpose="Post and review journals.",
                layout_pattern="columnar-worklist",
                states=("idle", "loading", "empty", "error", "disabled"),
            ),
        ),
    )
    if not overrides:
        return req
    data = req.__dict__.copy()
    data.update(overrides)
    return CompileRequest(**data)


def test_byte_stable_for_identical_inputs() -> None:
    first = compile_generation_prompt(_valid_request())
    second = compile_generation_prompt(_valid_request())
    assert first.prompt_body == second.prompt_body
    assert first.content_hash == second.content_hash
    assert (
        first.content_hash
        == hashlib.sha256(first.prompt_body.encode("utf-8")).hexdigest()
    )


def test_refuses_missing_art_direction() -> None:
    with pytest.raises(CompileRefusedError) as captured:
        compile_generation_prompt(_valid_request(art_direction=None))
    err = captured.value
    assert err.error_code == "CONTEXT_INCOMPLETE"
    assert err.retryable is False
    assert err.details is not None
    assert err.details["missing_artifact"] == "art_direction"


def test_refuses_unresolved_tokens_pin() -> None:
    with pytest.raises(CompileRefusedError) as captured:
        compile_generation_prompt(_valid_request(tokens_hash="0" * 64))
    err = captured.value
    assert err.error_code == "CONTEXT_INCOMPLETE"
    assert err.details is not None
    assert err.details["missing_artifact"] == "tokens"


def test_refuses_unknown_playbook_version() -> None:
    with pytest.raises(CompileRefusedError) as captured:
        compile_generation_prompt(_valid_request(playbook_version="9.9"))
    err = captured.value
    assert err.error_code == "CONTEXT_INCOMPLETE"
    assert err.details is not None
    assert err.details["missing_artifact"] == "playbook"


def test_refuses_unknown_tokens_version() -> None:
    with pytest.raises(CompileRefusedError) as captured:
        compile_generation_prompt(_valid_request(tokens_version=99))
    err = captured.value
    assert err.error_code == "CONTEXT_INCOMPLETE"
    assert err.details is not None
    assert err.details["missing_artifact"] == "tokens"


def test_refuses_when_no_approved_requirements() -> None:
    draft_only = (
        RequirementInput(
            requirement_id="req-draft",
            slug="REQ-LL-000",
            statement="Not yet approved.",
            status="draft",
        ),
    )
    with pytest.raises(CompileRefusedError) as captured:
        compile_generation_prompt(_valid_request(requirements=draft_only))
    err = captured.value
    assert err.error_code == "CONTEXT_INCOMPLETE"
    assert err.details is not None
    assert err.details["missing_artifact"] == "requirements"


def test_refuses_missing_dials() -> None:
    art = _valid_art_direction()
    del art["dials"]  # type: ignore[misc]
    with pytest.raises(CompileRefusedError) as captured:
        compile_generation_prompt(_valid_request(art_direction=art))
    err = captured.value
    assert err.error_code == "CONTEXT_INCOMPLETE"
    assert err.details is not None
    assert err.details["missing_artifact"] == "art_direction"


def test_refuses_missing_design_read() -> None:
    art = _valid_art_direction()
    art["design_read"] = ""
    with pytest.raises(CompileRefusedError) as captured:
        compile_generation_prompt(_valid_request(art_direction=art))
    err = captured.value
    assert err.error_code == "CONTEXT_INCOMPLETE"
    assert err.details is not None
    assert err.details["missing_artifact"] == "art_direction"


def test_refuses_palette_role_hex() -> None:
    art = _valid_art_direction()
    roles = dict(art["palette_roles"])  # type: ignore[arg-type]
    roles["accent"] = "#7c3aed"
    art["palette_roles"] = roles
    with pytest.raises(CompileRefusedError) as captured:
        compile_generation_prompt(_valid_request(art_direction=art))
    err = captured.value
    assert err.error_code == "CONTEXT_INCOMPLETE"
    assert err.details is not None
    assert err.details["missing_artifact"] == "art_direction"


def test_refuses_inter_display_without_explicit_flag() -> None:
    art = _valid_art_direction()
    art["type_pairing"] = {
        "pairing_id": "inter-explicit",
        "display": "Inter",
        "body": "Inter",
    }
    with pytest.raises(CompileRefusedError) as captured:
        compile_generation_prompt(_valid_request(art_direction=art))
    err = captured.value
    assert err.error_code == "CONTEXT_INCOMPLETE"
    assert err.details is not None
    assert err.details["missing_artifact"] == "art_direction"


def test_refuses_unknown_layout_pattern() -> None:
    features = (
        FeatureSurface(
            feature_id="feat-orphan",
            title="Orphan",
            purpose="Improvised grammar.",
            layout_pattern="centered-hero-three-cards",
            states=("idle", "loading", "empty", "error", "disabled"),
        ),
    )
    with pytest.raises(CompileRefusedError) as captured:
        compile_generation_prompt(_valid_request(features=features))
    err = captured.value
    assert err.error_code == "CONTEXT_INCOMPLETE"
    assert err.details is not None
    assert err.details["missing_artifact"] == "layout_pattern"


def test_prompt_embeds_every_never() -> None:
    prompt = compile_generation_prompt(_valid_request()).prompt_body
    nevers = json.loads((DESIGN / "nevers.json").read_text(encoding="utf-8"))
    for item in nevers["items"]:
        assert item["id"] in prompt
        assert item["statement"] in prompt


def test_prompt_cannot_instruct_off_token_values() -> None:
    prompt = compile_generation_prompt(_valid_request()).prompt_body
    allowed = _palette_literals()
    for match in HEX_RE.findall(prompt) + RGB_RE.findall(prompt):
        assert match in allowed, f"off-token colour in prompt: {match}"
    assert "use only token names" in prompt.lower() or (
        "token-sheet" in prompt.lower() and "off-token" in prompt.lower()
    )


def test_prompt_records_prd_feature_provenance() -> None:
    artifact = compile_generation_prompt(_valid_request())
    prov = artifact.provenance
    assert prov["prd_id"] == "prd-ledgerline"
    assert prov["requirement_slugs"] == ["REQ-LL-001"]
    assert prov["feature_ids"] == ["feat-journals"]
    assert prov["art_direction_id"] == "ad-ledgerline-1"
    body = artifact.prompt_body
    assert "prd-ledgerline" in body
    assert "REQ-LL-001" in body
    assert "feat-journals" in body
    assert "columnar-worklist" in body


def test_prompt_embeds_dials_and_design_read() -> None:
    art = _valid_art_direction()
    body = compile_generation_prompt(_valid_request()).prompt_body
    assert art["design_read"] in body
    assert "DESIGN_VARIANCE: 6" in body
    assert "MOTION_INTENSITY: 4" in body
    assert "VISUAL_DENSITY: 7" in body


def test_preview_html_comes_from_product_sheet() -> None:
    artifact = compile_generation_prompt(_valid_request())
    html = artifact.preview_html
    assert "cdn." not in html.lower()
    assert "taste-skill" not in html.lower()
    assert "impeccable" not in html.lower()
    assert artifact.art_direction_id in html


def test_compile_path_has_no_network_or_model_imports() -> None:
    banned = {
        "httpx",
        "requests",
        "urllib",
        "aiohttp",
        "openai",
        "anthropic",
        "socket",
        "httplib",
    }
    for path in STUDIO.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    assert root not in banned, f"{path.name} imports {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".", 1)[0]
                assert root not in banned, f"{path.name} imports {node.module}"


def test_compile_path_does_not_mint_graphs() -> None:
    forbidden_modules = {
        "engine.planning.service",
        "engine.planning.registry",
        "engine.planning.planner",
    }
    for path in STUDIO.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in forbidden_modules:
                raise AssertionError(f"{path.name} imports {node.module}")


def test_compile_path_does_not_load_third_party_design_skills() -> None:
    haystack = "\n".join(
        path.read_text(encoding="utf-8") for path in STUDIO.glob("*.py")
    ).lower()
    for needle in (
        "taste-skill",
        "leonxlnx",
        "web-design-guidelines",
        "agent-skills",
        "impeccable",
        "ui/ux pro max",
    ):
        assert needle not in haystack


def test_playbook_version_pin_matches_playbook_header() -> None:
    header = PLAYBOOK.read_text(encoding="utf-8").splitlines()[2]
    assert "**Version:** 1.2" in header
    compile_generation_prompt(_valid_request(playbook_version="1.2"))


def test_design_schemas_are_json_schema_2020_12() -> None:
    for name in ("art_direction.schema.json", "generation_prompt.schema.json"):
        payload = json.loads((DESIGN / name).read_text(encoding="utf-8"))
        assert payload["$schema"] == "https://json-schema.org/draft/2020-12/schema"
