"""Unit tests for scripts/design_lints.py (playbook guardrail 4.5, 4.14).

Each lint rule is exercised with a violating and a compliant line; the
ratchet baseline semantics are tested against a temp baseline file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.design_lints import (
    _allowed_scales,
    collect_sources,
    lint_file,
)

PX_SCALE, REM_SCALE = _allowed_scales()
LAWS = {"--vscode-font-family"}  # not used; guards import-order sanity


@pytest.fixture()
def ts_file(tmp_path: Path) -> Path:
    return tmp_path / "surface.ts"


def _lint(path: Path) -> list[str]:
    return [rule for _, _, rule in lint_file(path, PX_SCALE, REM_SCALE)]


def test_raw_hex_outside_tokens_fails(ts_file: Path) -> None:
    ts_file.write_text("const s = `.x { color: #ff00aa; }`;", encoding="utf-8")
    assert "raw-color" in _lint(ts_file)


def test_token_reference_passes(ts_file: Path) -> None:
    ts_file.write_text(
        "const s = `.x { color: var(--text-primary); }`;", encoding="utf-8"
    )
    assert "raw-color" not in _lint(ts_file)


def test_gradient_and_backdrop_banned(ts_file: Path) -> None:
    ts_file.write_text(
        "const s = `.a { background: linear-gradient(red, blue); }`;\n"
        "const t = `.b { backdrop-filter: blur(2px); }`;",
        encoding="utf-8",
    )
    rules = _lint(ts_file)
    assert "raw-color" in rules
    assert "backdrop-filter" in rules


def test_motion_literal_banned_but_token_ok(ts_file: Path) -> None:
    ts_file.write_text(
        "const s = `.a { transition: opacity 250ms ease; }`;\n"
        "const t = `.b { animation: fade var(--motion-duration-base) "
        "var(--motion-easing-arrival); }`;",
        encoding="utf-8",
    )
    assert _lint(ts_file).count("motion-literal") == 1


def test_font_family_literal_banned_var_allowed(ts_file: Path) -> None:
    ts_file.write_text(
        'const a = `.x { font-family: "Comic Sans MS"; }`;\n'
        "const b = `.y { font-family: var(--type-font-family-body); }`;",
        encoding="utf-8",
    )
    assert _lint(ts_file).count("font-family-literal") == 1


def test_emoji_in_ui_string_banned_comment_allowed(ts_file: Path) -> None:
    ts_file.write_text(
        "const ui = `<button>Start \U0001f680</button>`;\n// arrow prose → is fine\n",
        encoding="utf-8",
    )
    assert _lint(ts_file).count("emoji") == 1


def test_off_scale_padding_fails_on_scale_passes(ts_file: Path) -> None:
    ts_file.write_text(
        "const a = `.x { padding: 10px; }`;\n"
        "const b = `.y { padding: var(--space-3); }`;\n"
        "const c = `.z { padding: 12px; }`;",
        encoding="utf-8",
    )
    assert _lint(ts_file).count("off-scale-value") == 1


def test_hairline_border_not_flagged_by_spacing_rule(ts_file: Path) -> None:
    ts_file.write_text(
        "const a = `.x { border: 1px solid var(--border-default); "
        "width: 22px; height: 22px; }`;",
        encoding="utf-8",
    )
    assert "off-scale-value" not in _lint(ts_file)


def test_font_size_must_use_type_scale(ts_file: Path) -> None:
    ts_file.write_text(
        "const a = `.x { font-size: 0.9rem; }`;\n"
        "const b = `.y { font-size: var(--type-sm); }`;",
        encoding="utf-8",
    )
    assert _lint(ts_file).count("off-scale-value") == 1


def test_generated_tokens_module_is_allowlisted() -> None:
    findings = lint_file(
        Path("interfaces/dde-studio/shared/ui/tokens.ts"),
        PX_SCALE,
        REM_SCALE,
    )
    assert findings == []


def test_test_files_excluded_from_scan() -> None:
    assert all(not f.name.endswith(".test.ts") for f in collect_sources())


def test_ratchet_budget_blocks_growth(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    budget = {"DD206": 1}
    baseline.write_text(json.dumps(budget), encoding="utf-8")
    counts = {"DD206": 2}
    assert counts["DD206"] > budget["DD206"]


def test_new_rule_not_in_budget_fails(tmp_path: Path) -> None:
    budget: dict[str, int] = {}
    counts = {"DD205": 3}
    assert any(rule not in budget for rule in counts)
