"""Contract tests for CapturedProviderCredential — raw secret never a field."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from engine.contracts.captured_provider_credential import CapturedProviderCredential
from engine.core.ids import uuid7


def _now() -> datetime:
    return datetime.now(UTC)


def _valid_payload() -> dict[str, object]:
    now = _now()
    return {
        "capture_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "provider_id": "opensandbox_api_key",
        "secret_hash": "a" * 64,
        "fingerprint": "a" * 12,
        "last4": "wxyz",
        "status": "CAPTURED",
        "captured_by": "principal:test",
        "captured_at": now,
        "created_at": now,
        "updated_at": now,
    }


def test_captured_provider_credential_validates() -> None:
    record = CapturedProviderCredential.model_validate(_valid_payload())
    assert record.domain is None
    assert record.status == "CAPTURED"


def test_captured_provider_credential_rejects_secret_value_field() -> None:
    payload = _valid_payload()
    payload["secret_value"] = "raw-api-key-must-not-exist"  # noqa: S105
    with pytest.raises(ValidationError):
        CapturedProviderCredential.model_validate(payload)


def test_captured_provider_credential_rejects_api_key_field() -> None:
    payload = _valid_payload()
    payload["api_key"] = "raw-api-key-must-not-exist"  # noqa: S105
    with pytest.raises(ValidationError):
        CapturedProviderCredential.model_validate(payload)
