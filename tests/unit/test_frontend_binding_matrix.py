"""DDE-069 — the binding ledger must stay honest and in sync.

The matrix is only worth having if a row cannot claim more than the code
delivers. These tests enforce that mechanically: a `BOUND` row must name
production files that exist, a `VERIFIED` row must additionally name
tests that exist, and the rendered markdown must match the registry.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.context.repo import repo_root
from engine.core.errors import DdeError
from engine.studio.binding_matrix import (
    MATRIX_RELATIVE,
    RENDERED_RELATIVE,
    BindingStatus,
    integrity_findings,
    load_matrix,
    render_markdown,
)


def test_registry_loads_and_satisfies_its_integrity_rules() -> None:
    root = repo_root()
    matrix = load_matrix(root)
    assert matrix.rows, "the ledger must not be empty"
    findings = integrity_findings(matrix, root)
    assert findings == (), "\n".join(findings)


def test_rendered_markdown_is_in_sync_with_the_registry() -> None:
    root = repo_root()
    rendered = render_markdown(load_matrix(root))
    current = (root / RENDERED_RELATIVE).read_text(encoding="utf-8")
    assert current == rendered, (
        f"{RENDERED_RELATIVE} is stale; run "
        "`uv run python -m scripts.render_binding_matrix`"
    )


def test_every_golden_region_of_the_specification_has_rows() -> None:
    """Section 8 of FRONTEND_STUDIO_REV3 names ten binding regions. A
    region silently losing all its rows would hide missing work."""
    matrix = load_matrix(repo_root())
    expected = {
        "global_top_bar",
        "app_rail_and_explorer",
        "orchestrator_card",
        "canvas_toolbar",
        "canvas",
        "frontend_chat",
        "candidate_dock",
        "source_blend",
        "inspector",
        "status_bar",
    }
    assert {region.id for region in matrix.regions} == expected
    for region in matrix.regions:
        assert matrix.rows_for(region.id), f"region {region.id} has no rows"


def test_row_ids_are_unique_and_every_row_declares_a_visual_contract() -> None:
    matrix = load_matrix(repo_root())
    ids = [row.id for row in matrix.rows]
    assert len(ids) == len(set(ids))
    for row in matrix.rows:
        assert row.visual_contract.strip(), row.id


def test_claims_beyond_the_code_are_rejected(tmp_path) -> None:
    """Prove the integrity check bites, rather than only ever passing on a
    ledger whose rows all still read UNBOUND."""
    base = {
        "matrix_version": 1,
        "authority": "a",
        "closure_rule": "c",
        "regions": [{"id": "r", "title": "R", "specification": "s"}],
        "rows": [],
    }

    def findings_for(row: dict[str, object]) -> tuple[str, ...]:
        (tmp_path / "docs" / "truth" / "golden").mkdir(parents=True, exist_ok=True)
        (tmp_path / MATRIX_RELATIVE).write_text(
            json.dumps({**base, "rows": [row]}), encoding="utf-8"
        )
        return integrity_findings(load_matrix(tmp_path), tmp_path)

    template: dict[str, object] = {
        "id": "X-01",
        "region": "r",
        "feature": "f",
        "visual_contract": "v",
        "read_model": "SomeSnapshot",
        "command": None,
        "state_transition": None,
        "capability": None,
        "permission": "p",
        "failure_states": [],
        "implementation_refs": [],
        "tests": [],
        "status": "UNBOUND",
        "note": "",
    }

    assert findings_for(template) == ()

    bound_without_refs = {**template, "status": "BOUND"}
    assert any(
        "implementation_refs" in item for item in findings_for(bound_without_refs)
    )

    bound_with_ghost_ref = {
        **template,
        "status": "BOUND",
        "implementation_refs": ["engine/studio/does_not_exist.py"],
    }
    assert any("not found" in item for item in findings_for(bound_with_ghost_ref))

    verified_without_tests = {
        **template,
        "status": "VERIFIED",
        "implementation_refs": ["docs/truth/golden/frontend_binding_matrix.json"],
    }
    assert any(
        "names no tests" in item for item in findings_for(verified_without_tests)
    )

    unavailable_without_note = {**template, "status": "TYPED_UNAVAILABLE"}
    assert any(
        "without a note" in item for item in findings_for(unavailable_without_note)
    )

    bound_without_binding = {
        **template,
        "status": "BOUND",
        "read_model": None,
        "command": None,
        "implementation_refs": ["docs/truth/golden/frontend_binding_matrix.json"],
    }
    assert any(
        "neither a read model nor a command" in item
        for item in findings_for(bound_without_binding)
    )


def test_missing_registry_is_refused_not_defaulted(tmp_path: Path) -> None:
    with pytest.raises(DdeError) as excinfo:
        load_matrix(tmp_path)
    assert excinfo.value.error_code == "CONTEXT_INCOMPLETE"


def test_status_vocabulary_is_closed() -> None:
    matrix = load_matrix(repo_root())
    for row in matrix.rows:
        assert isinstance(row.status, BindingStatus)
