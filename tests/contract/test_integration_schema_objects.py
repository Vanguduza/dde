"""Schema tests (Chapter 19.1) for the objects DDE-013 introduces:
`WriteScopeLease` and `IntegrationProposal` (`engine.integration`)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from engine.contracts.integration_proposal import IntegrationProposal
from engine.contracts.write_scope_lease import WriteScopeLease
from engine.core.ids import uuid7


def _now() -> datetime:
    return datetime.now(UTC)


def _valid_lease_payload() -> dict[str, object]:
    return {
        "lease_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "mission_id": uuid7(),
        "task_id": uuid7(),
        "scope_patterns": ["engine/routing/**"],
        "exclusive": True,
        "status": "RESERVED",
        "acquired_at": _now(),
        "expires_at": _now(),
        "created_at": _now(),
        "updated_at": _now(),
    }


def test_write_scope_lease_is_valid_with_only_required_fields() -> None:
    lease = WriteScopeLease.model_validate(_valid_lease_payload())
    assert lease.released_at is None


def test_write_scope_lease_rejects_missing_required_field() -> None:
    payload = _valid_lease_payload()
    del payload["scope_patterns"]
    with pytest.raises(ValidationError):
        WriteScopeLease.model_validate(payload)


def test_write_scope_lease_rejects_unknown_fields() -> None:
    payload = _valid_lease_payload()
    payload["extra"] = True
    with pytest.raises(ValidationError):
        WriteScopeLease.model_validate(payload)


def _valid_proposal_payload() -> dict[str, object]:
    return {
        "proposal_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "mission_id": uuid7(),
        "task_id": uuid7(),
        "task_attempt_id": uuid7(),
        "source_branch": "task/deadbeef-a",
        "base_revision": "0" * 40,
        "proposed_revision": "1" * 40,
        "diff_summary": "1 file(s) changed",
        "changed_paths": ["engine/routing/policy.py"],
        "scope_lease_id": uuid7(),
        "pre_integration_verification_ref": uuid7(),
        "status": "QUEUED",
        "attempts": 1,
        "created_at": _now(),
        "updated_at": _now(),
    }


def test_integration_proposal_is_valid_with_only_required_fields() -> None:
    proposal = IntegrationProposal.model_validate(_valid_proposal_payload())
    assert proposal.conflict_class is None


def test_integration_proposal_rejects_missing_required_field() -> None:
    payload = _valid_proposal_payload()
    del payload["pre_integration_verification_ref"]
    with pytest.raises(ValidationError):
        IntegrationProposal.model_validate(payload)


def test_integration_proposal_rejects_unknown_fields() -> None:
    payload = _valid_proposal_payload()
    payload["extra"] = True
    with pytest.raises(ValidationError):
        IntegrationProposal.model_validate(payload)
