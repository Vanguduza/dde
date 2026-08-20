"""Structural retriever (Chapter 5.2): "definition, references, call/
import neighbourhood".

Tree-sitter is listed in the blueprint's tooling but is **not** a
dependency of this project (`pyproject.toml` has no `tree-sitter`
package), and this mission may not add one without an explicit
dependency-addition decision (Chapter 9.6, AGENTS.md). This is a
**flagged, deliberate substitution**: Python's own `ast` module gives an
exact definition index for `.py` files with zero new dependencies, at the
cost of only understanding Python (Tree-sitter's multi-language grammar
support is out of reach here) and of the cruder reference-counting
heuristic below (a real reference index would resolve imports and call
graphs, not count substring occurrences).
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from engine.context.model import AUTHORITY_RANK_CODE, ContextItem, DiscoveryResult
from engine.context.repo import classify_categories, is_excluded, touches_scope
from engine.context.terms import extract_terms
from engine.contracts.task import Task

MAX_CANDIDATE_FILES = 60
MAX_SYMBOLS_PER_FILE = 200
MAX_RESULT_ITEMS = 10
MAX_CONTENT_CHARS = 2000
_DEF_NODE_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


@dataclass(frozen=True)
class _Symbol:
    qualname: str
    simple_name: str
    lineno: int
    end_lineno: int


def _iter_definitions(node: ast.AST, prefix: str = "") -> Iterator[_Symbol]:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, _DEF_NODE_TYPES):
            qualname = f"{prefix}{child.name}"
            end_lineno = (
                child.end_lineno if child.end_lineno is not None else child.lineno
            )
            yield _Symbol(
                qualname=qualname,
                simple_name=child.name,
                lineno=child.lineno,
                end_lineno=end_lineno,
            )
            yield from _iter_definitions(child, prefix=f"{qualname}.")


def _candidate_files(
    discovery: DiscoveryResult,
    *,
    root: Path,
    expected_write_scope: tuple[str, ...],
) -> list[Path]:
    seen: set[Path] = set()
    files: list[Path] = []

    def add_dir(candidate: Path) -> None:
        for child in sorted(candidate.rglob("*.py")):
            if len(files) >= MAX_CANDIDATE_FILES:
                return
            if is_excluded(child.relative_to(root)) or child in seen:
                continue
            seen.add(child)
            files.append(child)

    def add_entry(entry: str) -> None:
        candidate = (root / entry).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return
        if candidate.is_file() and candidate.suffix == ".py" and candidate not in seen:
            seen.add(candidate)
            files.append(candidate)
        elif candidate.is_dir():
            add_dir(candidate)

    for entry in discovery.resolved_paths:
        add_entry(entry)
    for entry in expected_write_scope:
        add_entry(entry)
    return files[:MAX_CANDIDATE_FILES]


def _term_match_score(term: str, simple_name: str) -> float:
    lowered = simple_name.lower()
    if term == lowered:
        return 1.0
    if term in lowered:
        return 0.6
    return 0.0


def retrieve(
    task: Task,
    discovery: DiscoveryResult,
    *,
    root: Path,
    expected_write_scope: tuple[str, ...],
) -> list[ContextItem]:
    terms = extract_terms(task)
    if not terms:
        return []
    scored: list[tuple[float, str, Path, _Symbol]] = []
    for path in _candidate_files(
        discovery, root=root, expected_write_scope=expected_write_scope
    ):
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        rel_path = path.relative_to(root).as_posix()
        symbols = list(_iter_definitions(tree))[:MAX_SYMBOLS_PER_FILE]
        for symbol in symbols:
            best = max(
                (_term_match_score(term, symbol.simple_name) for term in terms),
                default=0.0,
            )
            if best <= 0.0:
                continue
            reference_count = max(0, source.count(symbol.simple_name) - 1)
            score = best + min(reference_count, 5) * 0.05
            scored.append((score, rel_path, path, symbol))
    scored.sort(key=lambda entry: (-entry[0], entry[1], entry[3].qualname))
    items: list[ContextItem] = []
    for rank, (score, rel_path, path, symbol) in enumerate(
        scored[:MAX_RESULT_ITEMS], start=1
    ):
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        snippet = "\n".join(lines[symbol.lineno - 1 : symbol.end_lineno])[
            :MAX_CONTENT_CHARS
        ]
        content = f"{rel_path}::{symbol.qualname} (line {symbol.lineno})\n{snippet}"
        items.append(
            ContextItem(
                retriever="structural",
                key=f"symbol:{rel_path}::{symbol.qualname}",
                categories=classify_categories(rel_path, content),
                authority_rank=AUTHORITY_RANK_CODE,
                rank_in_retriever=rank,
                relevance=min(1.0, score),
                write_scope_match=touches_scope(rel_path, expected_write_scope),
                content=content,
                source_path=rel_path,
            )
        )
    return items
