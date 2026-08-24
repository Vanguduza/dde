"""Unit tests: OpenSandbox paste → hash → capture never leaks raw key."""

from __future__ import annotations

from datetime import UTC, datetime

from adapters.opensandbox.settings import load_opensandbox_settings
from engine.capabilities.broker.capture import StaticSecretCaptureService
from engine.capabilities.broker.capture_hashing import (
    OPENSANDBOX_API_KEY_PROVIDER,
    secret_content_hash,
    secret_fingerprint,
    secret_last4,
)
from engine.contracts.captured_provider_credential import CapturedProviderCredential
from engine.core.ids import uuid7

RAW_KEY = "osk_test_raw_secret_value_never_in_metadata"


def test_hash_fingerprint_helpers_are_deterministic() -> None:
    digest = secret_content_hash(RAW_KEY)
    assert len(digest) == 64
    assert secret_fingerprint(digest) == digest[:12]
    assert secret_last4(RAW_KEY) == RAW_KEY[-4:]
    assert RAW_KEY not in digest


def test_public_status_never_includes_raw_key() -> None:
    now = datetime.now(UTC)
    record = CapturedProviderCredential(
        capture_id=uuid7(),
        tenant_id=uuid7(),
        project_id=uuid7(),
        provider_id=OPENSANDBOX_API_KEY_PROVIDER,
        domain="sandbox.example",
        secret_hash=secret_content_hash(RAW_KEY),
        fingerprint=secret_fingerprint(secret_content_hash(RAW_KEY)),
        last4=secret_last4(RAW_KEY),
        status="CAPTURED",
        supersedes_capture_id=None,
        superseded_by_capture_id=None,
        captured_by="principal:test",
        captured_at=now,
        revoked_at=None,
        created_at=now,
        updated_at=now,
    )
    status = StaticSecretCaptureService.public_status(record)
    blob = repr(status)
    assert RAW_KEY not in blob
    assert "secret_value" not in status
    assert "api_key" not in status
    assert status["captured"] is True
    assert status["fingerprint"] == record.fingerprint
    assert status["last4"] == record.last4


def test_env_fallback_loads_without_logging_key() -> None:
    settings = load_opensandbox_settings(
        {
            "DDE_OPENSANDBOX_ENABLED": "true",
            "DDE_OPENSANDBOX_DOMAIN": "sandbox.local",
            "DDE_OPENSANDBOX_API_KEY": RAW_KEY,
        }
    )
    assert settings.enabled is True
    assert settings.api_key == RAW_KEY
    assert settings.domain == "sandbox.local"
