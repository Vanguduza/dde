"""Unit tests for engine.verification.prototypes (playbook §5.3, guard 16).

Pure filesystem + policy tests: no PostgreSQL. The runner wiring is
exercised by the guardrail suite's shape (assess -> flags -> demote); here
every finding kind is pinned deterministically.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.verification.prototypes import (
    assess_prototype_dir,
    merge_prototype_flags,
)


def _workspace(tmp_path: Path, manifest: object | None = None) -> Path:
    root = tmp_path / "ws"
    screens = root / "prototypes" / "screens"
    screens.mkdir(parents=True, exist_ok=True)
    (screens / "overview.ready.html").write_text("<html></html>", encoding="utf-8")
    (screens / "mission-control.running.html").write_text(
        "<html></html>", encoding="utf-8"
    )
    if manifest is not None:
        (root / "prototypes" / "flows.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
    return root


def _manifest(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "version": 1,
        "screens": [
            {"file": "overview.ready.html", "surface": "overview", "state": "ready"},
            {
                "file": "mission-control.running.html",
                "surface": "mission-control",
                "state": "running",
            },
        ],
        "flows": [
            {
                "id": "start-mission",
                "entry": "overview.ready.html",
                "steps": [
                    {
                        "from": "overview.ready.html",
                        "on": "[data-cmd='startMission']",
                        "to": "mission-control.running.html",
                    }
                ],
            }
        ],
    }
    base.update(overrides)
    return base


def test_absent_prototypes_dir_is_informational(tmp_path: Path) -> None:
    assessment = assess_prototype_dir(tmp_path / "empty")
    assert not assessment.violations


def test_valid_manifest_has_no_violations(tmp_path: Path) -> None:
    assessment = assess_prototype_dir(_workspace(tmp_path, _manifest()))
    assert assessment.violations == ()


def test_missing_manifest_is_violation(tmp_path: Path) -> None:
    assessment = assess_prototype_dir(_workspace(tmp_path))
    kinds = {f.kind for f in assessment.violations}
    assert "missing_manifest" in kinds


def test_unparsable_manifest_is_violation(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    (ws / "prototypes" / "flows.json").write_text("{nope", encoding="utf-8")
    kinds = {f.kind for f in assess_prototype_dir(ws).violations}
    assert "manifest_unparsable" in kinds


def test_dangling_transition_target_is_violation(tmp_path: Path) -> None:
    manifest = _manifest(
        flows=[
            {
                "id": "start-mission",
                "entry": "overview.ready.html",
                "steps": [
                    {
                        "from": "overview.ready.html",
                        "on": "[data-cmd='startMission']",
                        "to": "ghost.screen.html",
                    }
                ],
            }
        ]
    )
    assessment = assess_prototype_dir(_workspace(tmp_path, manifest))
    kinds = {f.kind for f in assessment.findings}
    assert "referenced_screen_missing" in kinds
    assert assessment.violations


def test_undeclared_screen_file_is_violation(tmp_path: Path) -> None:
    ws = _workspace(tmp_path, _manifest())
    extra = ws / "prototypes" / "screens" / "overview.broken.html"
    extra.write_text("<html></html>", encoding="utf-8")
    kinds = {f.kind for f in assess_prototype_dir(ws).violations}
    assert "undeclared_screen_file" in kinds


def test_declared_screen_missing_from_disk_is_violation(tmp_path: Path) -> None:
    manifest = _manifest(
        screens=[
            {"file": "overview.ready.html", "surface": "o", "state": "ready"},
            {"file": "ghost.state.html", "surface": "g", "state": "state"},
        ]
    )
    kinds = {
        f.kind for f in assess_prototype_dir(_workspace(tmp_path, manifest)).violations
    }
    assert "declared_screen_missing" in kinds


def test_empty_flows_and_bad_id_violate(tmp_path: Path) -> None:
    empty = assess_prototype_dir(_workspace(tmp_path, {"version": 1, "flows": []}))
    assert any(f.kind == "no_flows" for f in empty.violations)
    bad = assess_prototype_dir(
        _workspace(
            tmp_path,
            _manifest(
                flows=[{"id": "Bad_Id", "entry": "overview.ready.html", "steps": [[1]]}]
            ),
        )
    )
    kinds = {f.kind for f in bad.violations}
    assert "flow_id_invalid" in kinds
    assert "step_invalid" in kinds


def test_merge_preserves_base_flags(tmp_path: Path) -> None:
    assessment = assess_prototype_dir(_workspace(tmp_path, _manifest()))
    merged = merge_prototype_flags({"verifier": "x", "independent": True}, assessment)
    assert merged["verifier"] == "x"
    assert merged["independent"] is True
    assert "prototype_manifest_findings" in merged
