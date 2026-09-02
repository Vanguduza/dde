"""Instant content-hash / fingerprint helpers for static-secret capture."""

from __future__ import annotations

from engine.core.hashing import canonical_json, sha256_hex

OPENSANDBOX_API_KEY_PROVIDER = "opensandbox_api_key"
OPENROUTER_API_KEY_PROVIDER = "openrouter_api_key"
FINGERPRINT_LEN = 12


def secret_content_hash(secret: str) -> str:
    return sha256_hex(secret)


def secret_fingerprint(secret_hash: str) -> str:
    return secret_hash[:FINGERPRINT_LEN]


def secret_last4(secret: str) -> str:
    return secret[-4:]


def capture_request_hash(
    *,
    provider_id: str,
    secret_hash: str,
    domain: str | None,
    captured_by: str,
) -> str:
    return sha256_hex(
        canonical_json(
            {
                "provider_id": provider_id,
                "secret_hash": secret_hash,
                "domain": domain or "",
                "captured_by": captured_by,
            }
        )
    )
