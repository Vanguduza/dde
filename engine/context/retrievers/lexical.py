"""Lexical retriever (Chapter 5.2): "ripgrep over the working tree,
ranked by BM25". This machine has `rg` on PATH, but the devcontainer spec
this project targets is not guaranteed to, so this module always has a
working stdlib-only fallback (`re`-based line scanning) — a **flagged
Stage 1 simplification**: real BM25 term weighting is not implemented
either way; ranking is by simple per-file match-line count, which is a
coarser approximation the blueprint does not itself pin to an exact
formula.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from engine.context.model import AUTHORITY_RANK_CODE, ContextItem
from engine.context.repo import EXCLUDED_DIR_NAMES, classify_categories, touches_scope
from engine.context.terms import extract_terms
from engine.contracts.task import Task

MAX_RESULT_FILES = 10
MAX_LINES_PER_FILE = 6
MAX_FILE_BYTES = 1_000_000
SEARCHABLE_SUFFIXES = frozenset(
    {".py", ".md", ".json", ".sql", ".toml", ".yaml", ".yml", ".txt"}
)
RIPGREP_TIMEOUT_SECONDS = 20

MatchesByFile = dict[str, list[tuple[int, str]]]


def _ripgrep_available() -> bool:
    return shutil.which("rg") is not None


def _search_with_ripgrep(root: Path, terms: tuple[str, ...]) -> MatchesByFile:
    args = [
        "rg",
        "--line-number",
        "--no-heading",
        "--ignore-case",
        "--fixed-strings",
        "--path-separator",
        "/",
        "--max-filesize",
        str(MAX_FILE_BYTES),
    ]
    for name in EXCLUDED_DIR_NAMES:
        args.extend(["--glob", f"!{name}/**"])
    for term in terms:
        args.extend(["-e", term])
    args.append(".")
    try:
        result = subprocess.run(  # noqa: S603 -- fixed argv, no shell, `rg` resolved via PATH
            args,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=RIPGREP_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    matches: MatchesByFile = {}
    for line in result.stdout.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        rel_path, lineno_str, content = parts
        if not lineno_str.isdigit():
            continue
        rel_path = rel_path.removeprefix("./")
        matches.setdefault(rel_path, []).append((int(lineno_str), content.strip()))
    return matches


def _search_with_stdlib(root: Path, terms: tuple[str, ...]) -> MatchesByFile:
    lowered_terms = [term.lower() for term in terms]
    matches: MatchesByFile = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in SEARCHABLE_SUFFIXES:
            continue
        if any(part in EXCLUDED_DIR_NAMES for part in path.relative_to(root).parts):
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel_path = path.relative_to(root).as_posix()
        for lineno, raw_line in enumerate(text.splitlines(), start=1):
            lowered_line = raw_line.lower()
            if any(term in lowered_line for term in lowered_terms):
                matches.setdefault(rel_path, []).append((lineno, raw_line.strip()))
    return matches


def retrieve(
    task: Task,
    *,
    root: Path,
    expected_write_scope: tuple[str, ...],
    use_ripgrep: bool | None = None,
) -> list[ContextItem]:
    terms = extract_terms(task)
    if not terms:
        return []
    ripgrep = _ripgrep_available() if use_ripgrep is None else use_ripgrep
    matches = (
        _search_with_ripgrep(root, terms)
        if ripgrep
        else _search_with_stdlib(root, terms)
    )
    ranked = sorted(matches.items(), key=lambda entry: (-len(entry[1]), entry[0]))
    items: list[ContextItem] = []
    for rank, (rel_path, lines) in enumerate(ranked[:MAX_RESULT_FILES], start=1):
        excerpt = "\n".join(
            f"{lineno}: {content}" for lineno, content in lines[:MAX_LINES_PER_FILE]
        )
        items.append(
            ContextItem(
                retriever="lexical",
                key=f"file:{rel_path}",
                categories=classify_categories(rel_path, excerpt),
                authority_rank=AUTHORITY_RANK_CODE,
                rank_in_retriever=rank,
                relevance=min(1.0, len(lines) / 10),
                write_scope_match=touches_scope(rel_path, expected_write_scope),
                content=excerpt,
                source_path=rel_path,
            )
        )
    return items
