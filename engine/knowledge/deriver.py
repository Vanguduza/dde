"""Chapter 5.10 derived-edge computation (DDE-033).

Real, structural (not semantic) derivation over this repository's own
working tree -- the same Stage 1 corpus `engine.context.repo` uses for the
lexical/structural retrievers (Chapter 5.2), and the same "no model call"
constraint `engine.context.conflict`/`engine.context.critic` document
(Chapter 9.6: no new dependency; AGENTS.md forbids handing model-generated
code a long-lived credential -- this module never makes one).

Two of Chapter 5.10's four named derived-edge shapes are implemented:

1. ``file_to_module`` -- every `.py` file maps to the Python package
   (directory) that contains it. Purely structural: read from the
   filesystem tree, no parsing of file contents.
2. ``test_to_symbol`` -- a `tests/**/test_<name>.py` file maps to the
   `engine.<...>.<name>` module its filename names, when such a module
   file actually exists in the tree. This is a **naming-convention
   heuristic**, not real symbol-level static analysis (which would need a
   Python AST/import-graph walker this Stage 1 slice does not build) --
   flagged as a Stage 1 approximation of the blueprint's "test->symbol"
   edge, not the full precision a future mission's real analyzer could
   provide.

``symbol_to_symbol`` (real call-graph edges) and
``requirement_to_symbol_inferred`` (matching retrieved requirement text
to touched symbols) both need real static analysis or retrieval-history
correlation this Stage 1 slice does not have; they are a **flagged,
undone gap** here, not silently dropped -- a future mission adding a
Tree-sitter/AST-backed symbol index (the same one Chapter 5.2's structural
retriever would need to stop being a Stage 1 approximation) should compute
them for real rather than approximating further here.
"""

from __future__ import annotations

from pathlib import Path

from engine.context.repo import is_excluded, to_posix
from engine.knowledge.model import DerivedEdgeCandidate

DERIVER_VERSION = "stage1-structural-v1"


def _module_for_directory(directory: Path, root: Path) -> str | None:
    if directory == root:
        return None
    relative = directory.relative_to(root)
    parts = relative.parts
    if not parts:
        return None
    return ".".join(parts)


def derive_file_to_module_edges(root: Path) -> list[DerivedEdgeCandidate]:
    """Every real `.py` file under `root` (excluding vendored/build dirs)
    paired with the dotted module path of its containing package."""
    edges: list[DerivedEdgeCandidate] = []
    for path in sorted(root.rglob("*.py")):
        if is_excluded(path.relative_to(root)):
            continue
        module = _module_for_directory(path.parent, root)
        if module is None:
            continue
        relpath = to_posix(str(path.relative_to(root)))
        edges.append(
            DerivedEdgeCandidate(
                edge_type="file_to_module",
                source_key=f"file:{relpath}",
                target_key=f"module:{module}",
            )
        )
    return edges


def derive_test_to_symbol_edges(root: Path) -> list[DerivedEdgeCandidate]:
    """Naming-convention heuristic: `tests/**/test_<name>.py` maps to the
    first `**/<name>.py` module file found under `engine/` -- a real,
    input-dependent match against the actual tree, not a fabricated
    constant, but a Stage 1 approximation of true symbol resolution (see
    module docstring)."""
    engine_root = root / "engine"
    tests_root = root / "tests"
    if not engine_root.is_dir() or not tests_root.is_dir():
        return []
    module_files_by_name: dict[str, Path] = {}
    for path in sorted(engine_root.rglob("*.py")):
        if is_excluded(path.relative_to(root)) or path.name == "__init__.py":
            continue
        module_files_by_name.setdefault(path.stem, path)

    edges: list[DerivedEdgeCandidate] = []
    for path in sorted(tests_root.rglob("test_*.py")):
        if is_excluded(path.relative_to(root)):
            continue
        candidate_name = path.stem[len("test_") :]
        module_file = module_files_by_name.get(candidate_name)
        if module_file is None:
            continue
        module = _module_for_directory(module_file.parent, root)
        if module is None:
            continue
        test_relpath = to_posix(str(path.relative_to(root)))
        edges.append(
            DerivedEdgeCandidate(
                edge_type="test_to_symbol",
                source_key=f"file:{test_relpath}",
                target_key=f"module:{module}.{candidate_name}",
            )
        )
    return edges


def derive_all(root: Path) -> list[DerivedEdgeCandidate]:
    """Chapter 5.10 entry point: every derived edge this Stage 1 slice can
    compute for one recompute pass. Pure and deterministic -- filesystem
    reads only, no I/O beyond that, no model call."""
    return derive_file_to_module_edges(root) + derive_test_to_symbol_edges(root)
