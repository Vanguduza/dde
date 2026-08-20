"""Schema tests (Chapter 19.1) for the object DDE-019 introduces:
`CredentialHandle` (`engine.capabilities.broker`)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from engine.contracts.credential_handle import CredentialHandle
from engine.core.ids import uuid7


def _now() -> datetime:
    return datetime.now(UTC)


def _valid_handle_payload() -> dict[str, object]:
    now = _now()
    return {
        "handle_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "mission_id": uuid7(),
        "task_id": uuid7(),
        "lease_id": uuid7(),
        "capability_id": "capability.run_local_process",
        "provider_id": "local_secret",
        "resource_scope": {},
        "issued_by_policy_version": "capability-lease-v1",
        "secret_hash": "a" * 64,
        "status": "ISSUED",
        "issued_at": now,
        "expires_at": now + timedelta(minutes=15),
        "requested_by": "system:test",
        "created_at": now,
        "updated_at": now,
    }


def test_credential_handle_is_valid_with_only_required_fields() -> None:
    handle = CredentialHandle.model_validate(_valid_handle_payload())
    assert handle.worker_run_id is None
    assert handle.provider_ref is None
    assert handle.revoked_at is None
    assert handle.revocation_reason is None
    assert handle.supersedes_handle_id is None
    assert handle.superseded_by_handle_id is None


def test_credential_handle_never_carries_a_secret_value_field() -> None:
    """Chapter 14.3: audit records store metadata and hashes, never secret
    material -- the contract itself must not even have a place to put one."""
    payload = _valid_handle_payload()
    payload["secret_value"] = "should-never-be-a-real-field"  # noqa: S105
    with pytest.raises(ValidationError):
        CredentialHandle.model_validate(payload)


def test_credential_handle_rejects_missing_required_field() -> None:
    payload = _valid_handle_payload()
    del payload["secret_hash"]
    with pytest.raises(ValidationError):
        CredentialHandle.model_validate(payload)


def test_credential_handle_rejects_unknown_fields() -> None:
    payload = _valid_handle_payload()
    payload["extra"] = True
    with pytest.raises(ValidationError):
        CredentialHandle.model_validate(payload)


def test_credential_handle_rejects_unknown_status() -> None:
    """The status vocabulary is a real, closed enum -- see
    `engine.capabilities.broker.states`'s module docstring."""
    payload = _valid_handle_payload()
    payload["status"] = "ACTIVE"
    with pytest.raises(ValidationError):
        CredentialHandle.model_validate(payload)
