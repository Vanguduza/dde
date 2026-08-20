"""Schema tests (Chapter 19.1) for the objects DDE-021 introduces:
`DiffGateReport` and `DependencyAdmission` (`engine.integration`)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from engine.contracts.dependency_admission import DependencyAdmission
from engine.contracts.diff_gate_report import DiffGateReport
from engine.core.ids import uuid7


def _now() -> datetime:
    return datetime.now(UTC)


def _valid_report_payload() -> dict[str, object]:
    now = _now()
    return {
        "report_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "mission_id": uuid7(),
        "task_id": uuid7(),
        "proposal_id": uuid7(),
        "command_id": uuid7(),
        "idempotency_key": "diff-gate:test",
        "request_hash": "a" * 64,
        "base_revision": "0" * 40,
        "proposed_revision": "1" * 40,
        "changed_paths": ["engine/routing/policy.py"],
        "status": "EVALUATING",
        "findings": [],
        "quarantined": False,
        "sbom_document": {"bomFormat": "CycloneDX", "specVersion": "1.5"},
        "sbom_content_hash": "b" * 64,
        "created_at": now,
        "updated_at": now,
    }


def test_diff_gate_report_is_valid_with_only_required_fields() -> None:
    report = DiffGateReport.model_validate(_valid_report_payload())
    assert report.findings == []
    assert report.quarantined is False


def test_diff_gate_report_rejects_missing_required_field() -> None:
    payload = _valid_report_payload()
    del payload["sbom_content_hash"]
    with pytest.raises(ValidationError):
        DiffGateReport.model_validate(payload)


def test_diff_gate_report_rejects_unknown_fields() -> None:
    payload = _valid_report_payload()
    payload["extra"] = True
    with pytest.raises(ValidationError):
        DiffGateReport.model_validate(payload)


def test_diff_gate_report_rejects_unknown_status() -> None:
    payload = _valid_report_payload()
    payload["status"] = "QUARANTINED"
    with pytest.raises(ValidationError):
        DiffGateReport.model_validate(payload)


def test_diff_gate_report_rejects_unknown_gate_name() -> None:
    payload = _valid_report_payload()
    payload["findings"] = [
        {
            "gate": "not_a_chapter_gate",
            "tool": "x",
            "severity": "info",
            "blocking": True,
            "passed": True,
            "summary": "no",
        }
    ]
    with pytest.raises(ValidationError):
        DiffGateReport.model_validate(payload)


def _valid_admission_payload() -> dict[str, object]:
    now = _now()
    return {
        "admission_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "mission_id": uuid7(),
        "task_id": uuid7(),
        "report_id": uuid7(),
        "package_name": "httpx",
        "package_version": "0.27.0",
        "ecosystem": "pypi",
        "is_top_level": True,
        "maintenance_signal": "unknown",
        "provenance": "justified",
        "vulnerability_ids": [],
        "status": "ADMITTED",
        "created_at": now,
        "updated_at": now,
    }


def test_dependency_admission_is_valid_with_only_required_fields() -> None:
    admission = DependencyAdmission.model_validate(_valid_admission_payload())
    assert admission.licence is None
    assert admission.justification is None


def test_dependency_admission_rejects_missing_required_field() -> None:
    payload = _valid_admission_payload()
    del payload["package_name"]
    with pytest.raises(ValidationError):
        DependencyAdmission.model_validate(payload)


def test_dependency_admission_rejects_unknown_fields() -> None:
    payload = _valid_admission_payload()
    payload["extra"] = True
    with pytest.raises(ValidationError):
        DependencyAdmission.model_validate(payload)


def test_dependency_admission_rejects_unknown_status() -> None:
    payload = _valid_admission_payload()
    payload["status"] = "GRANTED"
    with pytest.raises(ValidationError):
        DependencyAdmission.model_validate(payload)
