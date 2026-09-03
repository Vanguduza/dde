"""Contract tests for the design-token SSOT pipeline (playbook guardrail 4.2).

The token sheet pins every leaf with `const`; the generator emits typed TS
plus the CSS :root block; --check fails on drift. These tests pin the
pipeline shape so token edits cannot silently skip regeneration.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOKENS_SCHEMA = ROOT / "schemas" / "design" / "tokens.json"
GENERATED_TS = ROOT / "interfaces" / "dde-studio" / "shared" / "ui" / "tokens.ts"


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_design_tokens", ROOT / "scripts" / "generate_design_tokens.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def generator():
    return _load_generator()


def test_token_sheet_pins_every_leaf(generator) -> None:
    tokens = generator.load_tokens()

    def walk(schema: dict, path: str) -> None:
        if "const" in schema:
            return
        props = schema.get("properties")
        assert props, f"unpinned token leaf: {path}"
        for name, child in props.items():
            walk(child, f"{path}.{name}")

    for name, child in tokens.items():
        walk(child, name)


def test_semantic_aliases_resolve_to_palette_vars(generator) -> None:
    tokens = generator.load_tokens()
    palette = tokens["color"]["properties"]["palette"]["properties"]
    semantic = tokens["color"]["properties"]["semantic"]["properties"]
    kebab_palette = {
        "--" + "".join(("-" + c.lower()) if c.isupper() else c for c in name): value[
            "const"
        ]
        for name, value in palette.items()
    }
    for alias in semantic.values():
        target = alias["const"]
        assert target in kebab_palette, f"alias {target} not in palette"


def test_generated_ts_matches_current_sheet(generator) -> None:
    expected = generator._render_ts(generator.load_tokens())
    actual = GENERATED_TS.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert actual == expected


def test_check_detects_drift(generator, tmp_path: Path, monkeypatch) -> None:
    original = GENERATED_TS.read_text(encoding="utf-8")
    try:
        GENERATED_TS.write_text(original + "\n// drift\n", encoding="utf-8")
        assert generator.check(generator.render()) == 1
    finally:
        GENERATED_TS.write_text(original, encoding="utf-8")
    assert generator.check(generator.render()) == 0


def test_reduced_motion_media_query_zeroes_all_durations(generator) -> None:
    # DDE-068 residual (gap-closure-record.md §6.5): "reduced-motion
    # blocking assertions" require the product to *actually* respect
    # prefers-reduced-motion, not just a test-time screenshot emulation.
    # Every --motion-duration-* token must be overridden to 0ms inside a
    # real @media (prefers-reduced-motion: reduce) block so any component
    # already using the token automatically degrades, with no per-component
    # media query needed.
    tokens = generator.load_tokens()
    duration_names = list(
        tokens["motion"]["properties"]["duration"]["properties"].keys()
    )
    assert duration_names, "expected at least one motion duration token"
    rendered = generator._render_ts(tokens)
    assert "@media (prefers-reduced-motion: reduce)" in rendered
    media_block = rendered.split("@media (prefers-reduced-motion: reduce)", 1)[1]
    for name in duration_names:
        var_name = f"--motion-duration-{generator._kebab(name)}"
        assert f"{var_name}: 0ms;" in media_block, (
            f"{var_name} not zeroed inside the reduced-motion media block"
        )


def test_reduced_motion_block_matches_current_generated_file(generator) -> None:
    expected = generator._render_ts(generator.load_tokens())
    actual = GENERATED_TS.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert "@media (prefers-reduced-motion: reduce)" in actual
    assert actual == expected


def test_new_palette_token_flows_into_generated_output(
    generator, tmp_path: Path, monkeypatch
) -> None:
    sheet = json.loads(TOKENS_SCHEMA.read_text(encoding="utf-8"))
    palette = sheet["properties"]["color"]["properties"]["palette"]
    assert "testProbe" not in palette["properties"]
    palette["properties"]["testProbe"] = {"const": "#0a0b0c"}
    palette["required"] = [*palette["required"], "testProbe"]
    probe_schema = tmp_path / "tokens_probe.json"
    probe_schema.write_text(json.dumps(sheet), encoding="utf-8")
    monkeypatch.setattr(generator, "TOKENS_SCHEMA", probe_schema, raising=True)
    rendered = generator._render_ts(generator.load_tokens())
    assert '"testProbe": "#0a0b0c"' in rendered
    assert "--test-probe: #0a0b0c" in rendered
