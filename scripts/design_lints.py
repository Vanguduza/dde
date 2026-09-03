"""Static design lints over dde-studio UI sources (playbook guardrail 4.5).

DDE styles live inside TS template strings, so the stylelint strict-value
pattern is ported as a stdlib text scanner: raw colors, gradients,
backdrop-filter, motion literals, font-family literals, emoji-as-UI, and
off-scale spacing/font values are banned outside the generated tokens
module. Exit 1 with file:line findings.

DD207 (gap-closure-record.md §6.5; DDE-068 residual "combination lints")
is a whole-file rule layered on top of DD201-206's per-line rules: it flags
the specific generic-AI-tell fingerprint named in the playbook -- an
Inter-only font, an indigo/violet gradient, and a repeated 3-card block --
only when all three co-occur in one file. Any one or two alone is not
flagged; DD201/DD204 already police the raw literals individually.

Ratchet mode (--baseline): guardrail 4.14 lets legacy surfaces carry a
committed violation budget per rule that may only shrink; any count above
baseline fails. Without --baseline the law is absolute zero.
"""

from __future__ import annotations

import argparse
import colorsys
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDIO_SHARED = ROOT / "interfaces" / "dde-studio" / "shared"
TOKENS_SCHEMA = ROOT / "schemas" / "design" / "tokens.json"
GENERATED_TOKENS = STUDIO_SHARED / "ui" / "tokens.ts"
DEFAULT_BASELINE = ROOT / "docs" / "design" / "lint-baseline.json"

RAW_COLOR = re.compile(
    r"#[0-9a-fA-F]{3,8}\b"
    r"|rgba?\(\s*\d"
    r"|linear-gradient\("
    r"|radial-gradient\("
)
BACKDROP_FILTER = re.compile(r"backdrop-filter\s*:")
MOTION_PROP = re.compile(
    r"(?:transition|animation)(?:-duration|-timing-function)?\s*:[^;]*"
)
MOTION_VALUE = re.compile(r"\d*\.?\d+(?:ms|s)\b|cubic-bezier\(")
FONT_FAMILY_PROP = re.compile(r"(?<![\w-])font-family\s*:([^;]+)")
# Actual emoji/symbol blocks only; arrows and typographic marks in prose are
# copy, not UI iconography (§1.1 bans emoji *as icons/bullets/nav*).
EMOJI = re.compile(
    "[\U0001f300-\U0001faff\U00002700-\U000027bf\U0001f000-\U0001f0ff"
    "\U00002b00-\U00002bff\U0000fe0f]"
)
SPACING_PROPS = ("margin", "padding", "gap")
SPACING_PROP = re.compile(
    r"(?<![\w-])(" + "|".join(SPACING_PROPS) + r")(?:-[a-z]+)?\s*:([^;]*)"
)
FONT_SIZE_PROP = re.compile(r"(?<![\w-])font-size\s*:([^;]*)")
LENGTH = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(px|rem)")

RULE_IDS = {
    "raw-color": "DD201",
    "backdrop-filter": "DD202",
    "motion-literal": "DD203",
    "font-family-literal": "DD204",
    "emoji": "DD205",
    "off-scale-value": "DD206",
    "generic-tell-combination": "DD207",
}

# --- DD207 combination-lint detectors -------------------------------------
#
# Each leg is checked independently over the whole file; DD207 fires only
# when all three legs are present (see module docstring). The hue band was
# derived from the playbook's own example colors (#4f46e5 ~= 243 deg,
# #7c3aed ~= 262 deg) with headroom on each side, capped before magenta/pink
# (~300+ deg) so the rule stays specific to "indigo/violet".
INDIGO_VIOLET_HUE_MIN_DEGREES = 215.0
INDIGO_VIOLET_HUE_MAX_DEGREES = 300.0

INTER_FONT_FAMILY = re.compile(r"font-family\s*:\s*[\"']?Inter\b", re.IGNORECASE)
GRADIENT_FUNCTION = re.compile(r"(?:linear|radial)-gradient\(([^)]*)\)")
GRADIENT_HEX_STOP = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
CARD_CLASS_ATTR = re.compile(
    r'class(?:Name)?=["\']([^"\']*\bcard\b[^"\']*)["\']', re.IGNORECASE
)


def _hex_hue_degrees(hex_digits: str) -> float:
    if len(hex_digits) == 3:
        hex_digits = "".join(ch * 2 for ch in hex_digits)
    r = int(hex_digits[0:2], 16) / 255.0
    g = int(hex_digits[2:4], 16) / 255.0
    b = int(hex_digits[4:6], 16) / 255.0
    hue, _lightness, _saturation = colorsys.rgb_to_hls(r, g, b)
    return hue * 360.0


def _has_inter_font(text: str) -> bool:
    return bool(INTER_FONT_FAMILY.search(text))


def _has_indigo_violet_gradient(text: str) -> bool:
    for gradient in GRADIENT_FUNCTION.finditer(text):
        stops = GRADIENT_HEX_STOP.findall(gradient.group(1))
        if not stops:
            continue
        if any(
            INDIGO_VIOLET_HUE_MIN_DEGREES
            <= _hex_hue_degrees(stop)
            <= INDIGO_VIOLET_HUE_MAX_DEGREES
            for stop in stops
        ):
            return True
    return False


def _three_card_repetition_line(lines: list[str]) -> int | None:
    """First line of a class value that repeats 3+ times and names a card.

    A card grid legitimately repeats a class name; the fingerprint this
    rule targets is specifically *card*-shaped repetition (the playbook's
    "centered-hero-3-card" pattern), not any repeated class in general.
    """
    first_seen: dict[str, int] = {}
    counts: dict[str, int] = {}
    for lineno, line in enumerate(lines, start=1):
        for match in CARD_CLASS_ATTR.finditer(line):
            value = match.group(1).strip()
            if not value:
                continue
            counts[value] = counts.get(value, 0) + 1
            first_seen.setdefault(value, lineno)
    repeated = [value for value, count in counts.items() if count >= 3]
    if not repeated:
        return None
    return min(first_seen[value] for value in repeated)


ALLOWLIST_FILES = {GENERATED_TOKENS.resolve()}
EXCLUDED_SUFFIXES = (".test.ts",)


def _allowed_scales() -> tuple[set[str], set[str]]:
    data = json.loads(TOKENS_SCHEMA.read_text(encoding="utf-8"))
    spacing = data["properties"]["spacing"]["properties"]
    scale = data["properties"]["typography"]["properties"]["scale"]["properties"]
    px = {f"{float(s['const']):g}px" for s in spacing.values()}
    rem = {f"{float(s['const']):g}rem" for s in scale.values()}
    return px, rem


def _on_scale(value: str, unit: str, px_scale: set[str], rem_scale: set[str]) -> bool:
    normalized = f"{float(value):g}{unit}"
    return normalized in (px_scale if unit == "px" else rem_scale)


def lint_file(
    path: Path, px_scale: set[str], rem_scale: set[str]
) -> list[tuple[int, str, str]]:
    findings: list[tuple[int, str, str]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError):
        return findings
    generated = path.resolve() in ALLOWLIST_FILES
    for lineno, line in enumerate(lines, start=1):

        def add(rule: str, _lineno: int = lineno) -> None:
            findings.append((_lineno, RULE_IDS[rule], rule))

        if not generated:
            if RAW_COLOR.search(line):
                add("raw-color")
            if BACKDROP_FILTER.search(line):
                add("backdrop-filter")
            for match in FONT_FAMILY_PROP.finditer(line):
                if not match.group(1).lstrip().startswith("var("):
                    add("font-family-literal")
                    break
            for match in MOTION_PROP.finditer(line):
                if MOTION_VALUE.search(match.group(0)):
                    add("motion-literal")
                    break
        for match in SPACING_PROP.finditer(line):
            value_part = match.group(2)
            if "var(" in value_part:
                continue
            for lm in LENGTH.finditer(value_part):
                if not _on_scale(lm.group(1), lm.group(2), px_scale, rem_scale):
                    add("off-scale-value")
                    break
            else:
                continue
            break
        for match in FONT_SIZE_PROP.finditer(line):
            if "var(" in match.group(1):
                continue
            for lm in LENGTH.finditer(match.group(1)):
                if not _on_scale(lm.group(1), lm.group(2), px_scale, rem_scale):
                    add("off-scale-value")
                    break
            else:
                continue
            break
        if EMOJI.search(line) and not line.lstrip().startswith(("*", "//")):
            stripped = re.sub(r"<[^>]+>", "", line)
            stripped = re.sub(r"\$\{[^}]*\}", "", stripped)
            if EMOJI.search(stripped):
                add("emoji")

    if not generated:
        whole_file = "\n".join(lines)
        card_line = _three_card_repetition_line(lines)
        if (
            card_line is not None
            and _has_inter_font(whole_file)
            and _has_indigo_violet_gradient(whole_file)
        ):
            findings.append(
                (
                    card_line,
                    RULE_IDS["generic-tell-combination"],
                    "generic-tell-combination",
                )
            )

    return findings


def collect_sources() -> list[Path]:
    files: list[Path] = []
    for pattern in ("**/*.ts", "**/*.tsx", "**/*.css", "**/*.html"):
        files.extend(STUDIO_SHARED.glob(pattern))
    files = [
        f
        for f in files
        if not f.name.endswith(EXCLUDED_SUFFIXES) and f.resolve() not in ALLOWLIST_FILES
    ]
    return sorted(set(files))


def _counts(findings: list[tuple[Path, int, str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for _path, _lineno, rule_id, _rule in findings:
        counts[rule_id] = counts.get(rule_id, 0) + 1
    return counts


def _display_path(path: Path) -> Path:
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paths", nargs="*", help="restrict scan to these files")
    parser.add_argument(
        "--baseline",
        nargs="?",
        const=str(DEFAULT_BASELINE),
        help="enforce the committed shrink-only budget instead of zero",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="write current counts as the new budget (ratchet down only)",
    )
    args = parser.parse_args(argv)

    px_scale, rem_scale = _allowed_scales()
    files = [Path(p) for p in args.paths] if args.paths else collect_sources()
    findings: list[tuple[Path, int, str, str]] = []
    for path in files:
        for lineno, rule_id, rule in lint_file(path, px_scale, rem_scale):
            findings.append((path, lineno, rule_id, rule))

    for path, lineno, rule_id, rule in findings:
        print(f"{_display_path(path)}:{lineno}: {rule_id} {rule}", file=sys.stderr)

    counts = _counts(findings)
    print(f"design-lints: {len(findings)} violation(s) across {len(files)} file(s)")

    baseline_path = Path(args.baseline) if args.baseline else None
    if args.write_baseline and baseline_path is None:
        baseline_path = DEFAULT_BASELINE
    if args.write_baseline:
        existing: dict[str, int] = {}
        if baseline_path and baseline_path.exists():
            existing = json.loads(baseline_path.read_text(encoding="utf-8"))
        merged = {
            rule: min(existing.get(rule, counts.get(rule, 0)), counts.get(rule, 0))
            for rule in set(existing) | set(counts)
        }
        if baseline_path:
            baseline_path.parent.mkdir(parents=True, exist_ok=True)
            baseline_path.write_text(
                json.dumps(merged, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(f"baseline written: {baseline_path}")
        return 0

    if baseline_path:
        if not baseline_path.exists():
            print(f"missing baseline: {baseline_path}", file=sys.stderr)
            return 1
        budget = json.loads(baseline_path.read_text(encoding="utf-8"))
        failed = False
        for rule, allowed in sorted(budget.items()):
            actual = counts.get(rule, 0)
            if actual > allowed:
                print(
                    f"{rule}: {actual} > budget {allowed}",
                    file=sys.stderr,
                )
                failed = True
        for rule, actual in sorted(counts.items()):
            if rule not in budget:
                print(
                    f"{rule}: {actual} > budget 0 (new rule)",
                    file=sys.stderr,
                )
                failed = True
        return 1 if failed else 0

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
