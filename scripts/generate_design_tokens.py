"""Emit typed design tokens for dde-studio from schemas/design/tokens.json.

Playbook guardrail 4.2: the token sheet is the single source of truth; this
generator is its codegen leg, mirroring scripts.generate_contracts. The
generated module carries typed constants plus the CSS ``:root`` string
consumed by dde-studio's shared styles; hand edits fail ``--check``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOKENS_SCHEMA = ROOT / "schemas" / "design" / "tokens.json"
GENERATED_TS = ROOT / "interfaces" / "dde-studio" / "shared" / "ui" / "tokens.ts"


def load_tokens() -> dict[str, Any]:
    """The token sheet is a JSON Schema whose ``properties`` carry the
    values as ``const`` pins; shape validation lives in the contract test."""
    data = json.loads(TOKENS_SCHEMA.read_text(encoding="utf-8"))
    if data.get("title") != "DdeDesignTokens":
        raise TypeError(f"{TOKENS_SCHEMA} must be the DdeDesignTokens token sheet")
    return data["properties"]


def _const(schema: dict[str, Any], path: str) -> Any:
    if "const" not in schema:
        raise ValueError(f"token leaf must pin a value: {path}")
    return schema["const"]


def _kebab(name: str) -> str:
    out: list[str] = []
    for char in name:
        if char.isupper():
            out.append("-")
            out.append(char.lower())
        else:
            out.append(char)
    return "".join(out)


def _css_var_lines(tokens: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    palette = tokens["color"]["properties"]["palette"]["properties"]
    semantic = tokens["color"]["properties"]["semantic"]["properties"]
    for name in palette:
        lines.append(
            f"      --{_kebab(name)}: {_const(palette[name], f'color.{name}')};"
        )
    lines.append("")
    for alias, target_schema in semantic.items():
        target = str(_const(target_schema, f"color.semantic.{alias}"))
        lines.append(f"      --{_kebab(alias)}: var({target});")
    lines.append("")
    for name, schema in tokens["spacing"]["properties"].items():
        value = _const(schema, f"spacing.{name}")
        suffix = name.removeprefix("space")
        lines.append(f"      --space-{suffix}: {value}px;")
    lines.append("")
    for name, schema in tokens["radius"]["properties"].items():
        lines.append(f"      --radius-{_kebab(name)}: {_const(schema, name)}px;")
    lines.append("")
    for name, schema in tokens["shadow"]["properties"].items():
        lines.append(f"      --shadow-{_kebab(name)}: {_const(schema, name)};")
    lines.append("")
    typography = tokens["typography"]["properties"]
    body_font = _const(typography["fontFamilyBody"], "typography.fontFamilyBody")
    mono_font = _const(typography["fontFamilyMono"], "typography.fontFamilyMono")
    lines.append(f"      --type-font-family-body: {body_font};")
    lines.append(f"      --type-font-family-mono: {mono_font};")
    for name, schema in typography["scale"]["properties"].items():
        lines.append(
            f"      --type-{name}: {_const(schema, f'typography.scale.{name}')}rem;"
        )
    lines.append("")
    motion = tokens["motion"]["properties"]
    for kind in ("duration", "easing"):
        unit = "ms" if kind == "duration" else ""
        for name, schema in motion[kind]["properties"].items():
            lines.append(
                f"      --motion-{kind}-{_kebab(name)}: "
                f"{_const(schema, f'motion.{kind}.{name}')}{unit};"
            )
    lines.append("")
    for name, schema in tokens["zIndex"]["properties"].items():
        lines.append(f"      --z-{_kebab(name)}: {_const(schema, f'zIndex.{name}')};")
    return lines


def _record_literal(entries: list[tuple[str, Any]]) -> str:
    body = ",\n".join(f'  "{name}": {json.dumps(value)}' for name, value in entries)
    return "{\n" + body + "\n}"


def _render_ts(tokens: dict[str, Any]) -> str:
    palette_props = tokens["color"]["properties"]["palette"]["properties"]
    semantic_props = tokens["color"]["properties"]["semantic"]["properties"]
    spacing = [
        (f"space{name.removeprefix('space')}", _const(schema, name))
        for name, schema in tokens["spacing"]["properties"].items()
    ]
    duration_entries = [
        (name, _const(schema, name))
        for name, schema in tokens["motion"]["properties"]["duration"][
            "properties"
        ].items()
    ]
    easing_entries = [
        (name, _const(schema, name))
        for name, schema in tokens["motion"]["properties"]["easing"][
            "properties"
        ].items()
    ]

    sections: list[str] = [
        "// GENERATED from schemas/design/tokens.json. Do not edit.\n"
        "// Regenerate with: uv run python -m scripts.generate_design_tokens\n",
        "export const TOKENS_VERSION = 1;\n",
        "export const ColorPalette: Readonly<Record<string, string>> = "
        + _record_literal(
            [(name, _const(s, name)) for name, s in palette_props.items()]
        )
        + ";\n",
        "export const SemanticColors: Readonly<Record<string, string>> = "
        + _record_literal(
            [
                (f"--{_kebab(name)}", _const(s, name))
                for name, s in semantic_props.items()
            ]
        )
        + ";\n",
        "export const SpacingScalePx: Readonly<Record<string, number>> = "
        + _record_literal([(name, int(value)) for name, value in spacing])
        + ";\n",
        "export const RadiusScalePx: Readonly<Record<string, number>> = "
        + _record_literal(
            [
                (f"--radius-{_kebab(name)}", _const(s, name))
                for name, s in tokens["radius"]["properties"].items()
            ]
        )
        + ";\n",
        "export const Shadows: Readonly<Record<string, string>> = "
        + _record_literal(
            [
                (f"--shadow-{_kebab(name)}", _const(s, name))
                for name, s in tokens["shadow"]["properties"].items()
            ]
        )
        + ";\n",
        "export const Typography: Readonly<Record<string, unknown>> = "
        + json.dumps(
            {
                "fontFamilyBody": _const(
                    tokens["typography"]["properties"]["fontFamilyBody"], ""
                ),
                "fontFamilyMono": _const(
                    tokens["typography"]["properties"]["fontFamilyMono"], ""
                ),
                "scale": {
                    name: _const(s, name)
                    for name, s in tokens["typography"]["properties"]["scale"][
                        "properties"
                    ].items()
                },
            },
            indent=2,
        )
        + ";\n",
        "export const MotionDurationMs: Readonly<Record<string, number>> = "
        + _record_literal(duration_entries)
        + ";\n",
        "export const MotionEasing: Readonly<Record<string, string>> = "
        + _record_literal(easing_entries)
        + ";\n",
        "export const MotionIdentity: Readonly<Record<string, unknown>> = "
        + json.dumps(
            {
                name: {
                    key: _const(child, f"motion.identity.{name}.{key}")
                    for key, child in schema["properties"].items()
                }
                for name, schema in tokens["motion"]["properties"]["identity"][
                    "properties"
                ].items()
            },
            indent=2,
        )
        + ";\n",
        "export const ZLayers: Readonly<Record<string, number>> = "
        + _record_literal(
            [
                (f"--z-{_kebab(name)}", _const(s, name))
                for name, s in tokens["zIndex"]["properties"].items()
            ]
        )
        + ";\n",
    ]

    css_root_lines = _css_var_lines(tokens)
    ts_root_block = "\n".join(["    :root {", *css_root_lines, "    }"])
    sections.append(
        "/** CSS :root block consumed by sharedStyles(); codegen only. */\n"
        "export function tokenCssRoot(): string {\n"
        "  return `\n"
        f"{ts_root_block}\n"
        "  `;\n"
        "}\n"
    )
    return "\n".join(sections)


def render() -> dict[Path, str]:
    return {GENERATED_TS: _render_ts(load_tokens())}


def write(files: dict[Path, str]) -> None:
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")


def check(files: dict[Path, str]) -> int:
    failed = False
    for path, expected in files.items():
        if not path.exists():
            print(f"missing generated file: {path}", file=sys.stderr)
            failed = True
            continue
        actual = path.read_text(encoding="utf-8")
        if actual.replace("\r\n", "\n") != expected:
            print(f"generated drift: {path}", file=sys.stderr)
            failed = True
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    files = render()
    if args.check:
        return check(files)
    write(files)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
