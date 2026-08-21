"""Chapter 5.3 chunking for the semantic index.

Code chunks are cut on syntactic boundaries — a function, method, class or
top-level block, never a fixed token window — using Python's `ast` for
`.py` files (the same flagged substitution `engine.context.retrievers.
structural` already documents: Tree-sitter is not a dependency, and `ast`
gives an exact definition index for Python with zero new dependencies).
Documents (`.md`) chunk on heading boundaries. Every chunk carries
`file_path`, `symbol_path`, `start_line`, `end_line`, `language`,
`content_hash` — the identity fields Chapter 5.4 invalidates on.

**Flagged simplification.** Chunking covers Python and Markdown only (the
code + documentation corpus the semantic index serves). A size ceiling is
not enforced here because `ast` already splits at nested definition
boundaries and Markdown headings are their own natural boundary; a chunk
whose single syntactic unit is still oversized is kept whole rather than
split mid-statement, which Chapter 5.3 forbids.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from engine.core.hashing import sha256_hex

CHUNKABLE_SUFFIXES = frozenset({".py", ".md"})
MAX_FILE_BYTES = 1_000_000


@dataclass(frozen=True)
class Chunk:
    """One syntactic chunk. `content_hash` over `content` is part of the
    chunk identity (Chapter 5.4)."""

    file_path: str
    symbol_path: str
    start_line: int
    end_line: int
    language: str
    content: str

    @property
    def content_hash(self) -> str:
        return sha256_hex(self.content)


def _iter_python_chunks(path: Path, rel_path: str) -> list[Chunk]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError:
        return []
    lines = source.splitlines()
    chunks: list[Chunk] = []
    covered: list[tuple[int, int]] = []

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qualname = f"{prefix}{child.name}"
                end = child.end_lineno if child.end_lineno is not None else child.lineno
                content = "\n".join(lines[child.lineno - 1 : end])
                chunks.append(
                    Chunk(
                        file_path=rel_path,
                        symbol_path=qualname,
                        start_line=child.lineno,
                        end_line=end,
                        language="python",
                        content=content,
                    )
                )
                covered.append((child.lineno, end))
                visit(child, prefix=f"{qualname}.")
            elif isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                # Recurse so nested defs under control flow are still found.
                visit(child, prefix=prefix)

    visit(tree, prefix="")
    module_lines = _uncovered_lines(lines, covered)
    if module_lines:
        content = "\n".join(module_lines)
        if content.strip():
            chunks.append(
                Chunk(
                    file_path=rel_path,
                    symbol_path="<module>",
                    start_line=1,
                    end_line=len(lines),
                    language="python",
                    content=content,
                )
            )
    return chunks


def _uncovered_lines(lines: list[str], covered: list[tuple[int, int]]) -> list[str]:
    covered_set: set[int] = set()
    for start, end in covered:
        covered_set.update(range(start, end + 1))
    return [line for idx, line in enumerate(lines, start=1) if idx not in covered_set]


def _iter_markdown_chunks(path: Path, rel_path: str) -> list[Chunk]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    lines = source.splitlines()
    chunks: list[Chunk] = []
    current_heading = ""
    current_start = 1
    current: list[str] = []

    def flush(end_line: int) -> None:
        nonlocal current, current_start
        content = "\n".join(current)
        if content.strip():
            chunks.append(
                Chunk(
                    file_path=rel_path,
                    symbol_path=current_heading,
                    start_line=current_start,
                    end_line=end_line,
                    language="markdown",
                    content=content,
                )
            )
        current = []
        current_start = end_line + 1

    for lineno, line in enumerate(lines, start=1):
        if line.startswith("#"):
            flush(lineno - 1)
            current_heading = line.lstrip("#").strip() or rel_path
            current_start = lineno
        current.append(line)
    flush(len(lines))
    return chunks


def chunk_file(path: Path, rel_path: str) -> list[Chunk]:
    """Chunk a single file by suffix. Returns no chunks for unsupported or
    unreadable files."""
    if path.suffix not in CHUNKABLE_SUFFIXES:
        return []
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return []
    except OSError:
        return []
    if path.suffix == ".py":
        return _iter_python_chunks(path, rel_path)
    return _iter_markdown_chunks(path, rel_path)
