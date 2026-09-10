from __future__ import annotations

import json

import pytest

from scripts import repository_governance as governance


def _bug(bug_id: str = "DDE-BUG-0001") -> dict[str, object]:
    return {
        "schema_version": 1,
        "bug_id": bug_id,
        "status": "FIXED",
        "fixed_at_utc": "2026-09-10T12:00:00Z",
        "severity": "HIGH",
        "title": "A real fixed defect",
        "symptom": "The governed behavior failed.",
        "root_cause": "A contract boundary was incomplete.",
        "resolution": "The boundary was repaired and regression-tested.",
        "affected_scope": ["engine/example.py"],
        "regression_tests": ["tests/unit/test_example.py"],
        "evidence_refs": ["github-actions:run/1"],
        "fixed_by_commit": "SELF",
        "fix_subject": "fix(example): repair boundary",
    }


def test_side_branch_names_are_temporary_and_cannot_claim_authority() -> None:
    assert governance.validate_branch_name("feat/repository-governance") == []
    assert governance.validate_branch_name("fix/graph-determinism") == []
    assert governance.validate_branch_name("main") == []
    assert governance.validate_branch_name("developer/alice")
    assert governance.validate_branch_name("docs/canonical-rewrite")


def test_material_runtime_changes_require_changelog_classification() -> None:
    assert governance.material_change(["engine/runtime.py"], ["chore: touch runtime"])
    assert governance.material_change(["README.md"], ["feat: add behavior"])
    assert not governance.material_change(["README.md"], ["docs: clarify wording"])


def test_bug_ledger_requires_contiguous_unique_ids() -> None:
    assert governance.validate_bug_entries([_bug()]) == []
    errors = governance.validate_bug_entries([_bug("DDE-BUG-0002")])
    assert any("contiguous" in error for error in errors)
    errors = governance.validate_bug_entries([_bug(), _bug()])
    assert any("duplicate" in error for error in errors)


def test_bug_ledger_render_is_deterministic_and_readable() -> None:
    entry = _bug()
    rendered = governance.render_bug_ledger([entry])
    assert "# DDE Fixed-Bug Ledger" in rendered
    assert "DDE-BUG-0001" in rendered
    assert "**Root cause:** A contract boundary was incomplete." in rendered
    assert rendered == governance.render_bug_ledger([entry])


def test_fix_range_requires_changelog_and_bug_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(governance, "validate_static", lambda revision=None: [])
    monkeypatch.setattr(
        governance, "changed_files", lambda _base, _head: ["engine/x.py"]
    )
    monkeypatch.setattr(
        governance,
        "commit_subjects",
        lambda _base, _head: [("a" * 40, "fix(runtime): repair x")],
    )
    errors = governance.verify_range("base", "head")
    assert any("CHANGELOG.md" in error for error in errors)
    assert any("BUG_FIX_LEDGER.jsonl" in error for error in errors)


def test_bug_ledger_parser_rejects_non_object_lines() -> None:
    with pytest.raises(ValueError, match="must be a JSON object"):
        governance.parse_bug_entries(json.dumps(["not-an-entry"]))
