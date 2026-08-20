"""The DCE's Stage 1 corpus: this repository's own working tree.

Chapter 5.2 defines the lexical retriever as "ripgrep over the working
tree" and the structural retriever over a Tree-sitter symbol index of the
product repository. This project has no separate product-repo concept
yet — DDE does not manufacture a second codebase in Stage 1 — so the
lexical/structural/explicit retrievers all use this repository's own git
working tree as their corpus. **This is a flagged, deliberate Stage 1
simplification**, not the blueprint's intended shape once DDE manages an
external product repository.
"""

from __future__ import annotations

from pathlib import Path

EXCLUDED_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "node_modules",
        ".idea",
        ".vscode",
    }
)

# Keyword lists driving Chapter 5.8 coverage classification. These are
# Stage 1 heuristics — genuine, input-dependent signals derived from real
# retrieval content, not a fabricated always-the-same answer — standing in
# for the dedicated architecture/business-rule tables Chapter 3.3 does not
# create yet.
ARCHITECTURE_PATH_PREFIXES = ("docs/blueprint/", "AGENTS.md")
SECURITY_KEYWORDS = frozenset(
    {
        "security",
        "secret",
        "credential",
        "auth",
        "rls",
        "tenant",
        "permission",
        "encrypt",
        "capability",
        "lease",
    }
)


def repo_root() -> Path:
    """Locate this repository's own working tree root: three parents up
    from `engine/context/repo.py`."""
    return Path(__file__).resolve().parents[2]


def is_excluded(path: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def to_posix(path: str) -> str:
    return path.replace("\\", "/")


def normalized_relpath(path: Path, root: Path) -> str:
    return to_posix(str(path.relative_to(root)))


def touches_scope(path: str, scope: tuple[str, ...]) -> bool:
    """Is `path` within one of `scope`'s declared prefixes? Mirrors
    `engine.planning.validate.in_scope`'s semantics without importing a
    planning-internal helper across a module boundary."""
    normalized = to_posix(path).rstrip("/")
    for entry in scope:
        prefix = to_posix(entry).rstrip("/")
        if normalized == prefix or normalized.startswith(f"{prefix}/"):
            return True
    return False


def classify_categories(path: str, content: str) -> tuple[str, ...]:
    """Chapter 5.8 category tagging for code/document evidence. A single
    retrieved item can evidence more than one coverage category — e.g. an
    `AGENTS.md` hit about RLS evidences both `architecture_constraints`
    and `security_constraints`."""
    normalized = to_posix(path)
    categories: list[str] = []
    if any(normalized.startswith(prefix) for prefix in ARCHITECTURE_PATH_PREFIXES):
        categories.append("architecture_constraints")
    lowered = content.lower()
    if any(keyword in lowered for keyword in SECURITY_KEYWORDS):
        categories.append("security_constraints")
    if not categories:
        categories.append("impacted_code_and_deps")
    return tuple(categories)


def current_commit_sha(root: Path) -> str:
    """Best-effort current commit SHA, read directly from `.git` (no `git`
    executable required — Chapter 5.4 only needs `index_version` to be a
    real, stable value in Stage 1; there is no index build step yet)."""
    git_dir = root / ".git"
    head_file = git_dir / "HEAD"
    try:
        head = head_file.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"
    if not head.startswith("ref:"):
        return head or "unknown"
    ref_name = head.split(" ", 1)[1].strip()
    ref_path = git_dir / ref_name
    try:
        return ref_path.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    packed_refs = git_dir / "packed-refs"
    try:
        for line in packed_refs.read_text(encoding="utf-8").splitlines():
            if line.endswith(f" {ref_name}"):
                return line.split(" ", 1)[0]
    except OSError:
        pass
    return "unknown"
