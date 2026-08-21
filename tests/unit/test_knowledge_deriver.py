"""Chapter 5.10 derived-edge computation: structural, deterministic
derivation over a real (synthetic) working tree -- `engine.knowledge.deriver`."""

from __future__ import annotations

from pathlib import Path

from engine.knowledge.deriver import (
    derive_all,
    derive_file_to_module_edges,
    derive_test_to_symbol_edges,
)


def _build_tree(root: Path) -> None:
    (root / "engine" / "widgets").mkdir(parents=True, exist_ok=True)
    (root / "engine" / "widgets" / "__init__.py").write_text("", encoding="utf-8")
    (root / "engine" / "widgets" / "service.py").write_text(
        "def build() -> None:\n    pass\n", encoding="utf-8"
    )
    (root / "tests" / "unit").mkdir(parents=True, exist_ok=True)
    (root / "tests" / "unit" / "test_service.py").write_text(
        "def test_build() -> None:\n    pass\n", encoding="utf-8"
    )
    (root / "tests" / "unit" / "test_unmatched.py").write_text(
        "def test_nothing() -> None:\n    pass\n", encoding="utf-8"
    )
    (root / ".git").mkdir(parents=True, exist_ok=True)
    (root / "__pycache__").mkdir(parents=True, exist_ok=True)
    (root / "__pycache__" / "junk.py").write_text("junk", encoding="utf-8")


def test_file_to_module_edges_map_every_real_py_file_to_its_package(
    tmp_path: Path,
) -> None:
    _build_tree(tmp_path)

    edges = derive_file_to_module_edges(tmp_path)

    keys = {(edge.source_key, edge.target_key) for edge in edges}
    assert (
        "file:engine/widgets/service.py",
        "module:engine.widgets",
    ) in keys
    assert (
        "file:tests/unit/test_service.py",
        "module:tests.unit",
    ) in keys
    assert all(edge.edge_type == "file_to_module" for edge in edges)


def test_file_to_module_edges_exclude_vendored_and_cache_directories(
    tmp_path: Path,
) -> None:
    _build_tree(tmp_path)

    edges = derive_file_to_module_edges(tmp_path)

    assert not any("junk" in edge.source_key for edge in edges)


def test_test_to_symbol_matches_naming_convention_against_real_module(
    tmp_path: Path,
) -> None:
    _build_tree(tmp_path)

    edges = derive_test_to_symbol_edges(tmp_path)

    assert len(edges) == 1
    edge = edges[0]
    assert edge.edge_type == "test_to_symbol"
    assert edge.source_key == "file:tests/unit/test_service.py"
    assert edge.target_key == "module:engine.widgets.service"


def test_test_to_symbol_skips_tests_with_no_matching_module(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    edges = derive_test_to_symbol_edges(tmp_path)

    assert not any("test_unmatched" in edge.source_key for edge in edges)


def test_derive_all_combines_both_deriver_shapes(tmp_path: Path) -> None:
    _build_tree(tmp_path)

    edges = derive_all(tmp_path)

    edge_types = {edge.edge_type for edge in edges}
    assert edge_types == {"file_to_module", "test_to_symbol"}
