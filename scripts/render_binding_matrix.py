"""Render docs/truth/FRONTEND_STUDIO_BINDING_MATRIX.md from the registry.

`--check` verifies the rendered file is in sync and the ledger's integrity
rules hold, without writing. Mirrors `scripts/generate_contracts.py`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from engine.studio.binding_matrix import (
    RENDERED_RELATIVE,
    integrity_findings,
    load_matrix,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify sync and integrity instead of writing",
    )
    args = parser.parse_args(argv)

    matrix = load_matrix(ROOT)
    findings = integrity_findings(matrix, ROOT)
    rendered = render_markdown(matrix)
    target = ROOT / RENDERED_RELATIVE

    if args.check:
        for finding in findings:
            print(f"binding-matrix: {finding}", file=sys.stderr)
        current = target.read_text(encoding="utf-8") if target.is_file() else ""
        if current != rendered:
            print(
                f"binding-matrix: {RENDERED_RELATIVE} is out of date; run "
                "`uv run python -m scripts.render_binding_matrix`",
                file=sys.stderr,
            )
            return 1
        return 1 if findings else 0

    if findings:
        for finding in findings:
            print(f"binding-matrix: {finding}", file=sys.stderr)
        return 1
    target.write_text(rendered, encoding="utf-8")
    print(f"wrote {RENDERED_RELATIVE} ({len(matrix.rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
