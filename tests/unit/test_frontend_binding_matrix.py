"""DDE-069 — the binding ledger must stay honest and in sync.

The matrix is only worth having if a row cannot claim more than the code
delivers. These tests enforce that mechanically: backend/domain evidence
cannot certify a missing UI, every applicable layer is explicit, and the
rendered markdown must match the registry.
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
    EvidenceLayer,
    LayerStatus,
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
        "evidence": {
            "DOMAIN": {"status": "NOT_APPLICABLE", "refs": []},
            "READ": {
                "status": "BOUND",
                "refs": ["docs/truth/golden/frontend_binding_matrix.json"],
            },
            "COMMAND": {"status": "NOT_APPLICABLE", "refs": []},
            "UI": {"status": "UNBOUND", "refs": []},
            "WIRED": {"status": "UNBOUND", "refs": []},
            "E2E": {"status": "UNBOUND", "refs": []},
            "VISUAL": {"status": "UNBOUND", "refs": []},
        },
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
        assert row.status is row.derived_status()
        assert {item.layer for item in row.evidence} == set(EvidenceLayer)
        assert all(isinstance(item.status, LayerStatus) for item in row.evidence)


def test_backend_only_evidence_cannot_verify_a_visible_control(tmp_path: Path) -> None:
    root = repo_root()
    production_ref = "engine/studio/chat/service.py"
    test_ref = "tests/unit/test_frontend_chat_intent.py"
    document = {
        "matrix_version": 2,
        "authority": "authority",
        "closure_rule": "all applicable layers",
        "regions": [{"id": "chat", "title": "Chat", "specification": "spec"}],
        "rows": [
            {
                "id": "CH-X",
                "region": "chat",
                "feature": "Chat composer",
                "visual_contract": "Visible composer",
                "read_model": "FrontendConversation",
                "command": "frontend.chat.send",
                "state_transition": "turn appended",
                "capability": None,
                "permission": "project read",
                "failure_states": ["UNAVAILABLE"],
                "implementation_refs": [production_ref],
                "tests": [test_ref],
                "evidence": {
                    "DOMAIN": {
                        "status": "VERIFIED",
                        "refs": [production_ref, test_ref],
                    },
                    "READ": {
                        "status": "VERIFIED",
                        "refs": [production_ref, test_ref],
                    },
                    "COMMAND": {
                        "status": "VERIFIED",
                        "refs": [production_ref, test_ref],
                    },
                    "UI": {"status": "UNBOUND", "refs": []},
                    "WIRED": {"status": "UNBOUND", "refs": []},
                    "E2E": {"status": "UNBOUND", "refs": []},
                    "VISUAL": {"status": "UNBOUND", "refs": []},
                },
                "status": "VERIFIED",
                "note": "",
            }
        ],
    }
    matrix_path = tmp_path / MATRIX_RELATIVE
    matrix_path.parent.mkdir(parents=True)
    matrix_path.write_text(json.dumps(document), encoding="utf-8")
    for ref in (production_ref, test_ref):
        destination = tmp_path / ref
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (root / ref).read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    matrix = load_matrix(tmp_path)
    assert matrix.rows[0].derived_status() is BindingStatus.UNBOUND
    assert any(
        "final status VERIFIED does not match layer-derived UNBOUND" in finding
        for finding in integrity_findings(matrix, tmp_path)
    )
