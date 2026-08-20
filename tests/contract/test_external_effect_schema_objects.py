"""Schema tests (Chapter 19.1) for the object DDE-020 introduces:
`ExternalEffect` (`engine.recovery`)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from engine.contracts.external_effect import ExternalEffect
from engine.core.ids import uuid7


def _now() -> datetime:
    return datetime.now(UTC)


def _valid_effect_payload() -> dict[str, object]:
    now = _now()
    return {
        "effect_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "mission_id": uuid7(),
        "worker_run_id": uuid7(),
        "capability_lease_id": uuid7(),
        "command_id": uuid7(),
        "target_system": "local_process",
        "target_resource": "/tmp/ws",
        "operation": "python -c pass",
        "side_effect_class": "WORKSPACE_LOCAL",
        "idempotency_key": "run:effect:capability.run_local_process",
        "request_hash": "a" * 64,
        "status": "PREPARED",
        "created_at": now,
        "updated_at": now,
    }


def test_external_effect_is_valid_with_only_required_fields() -> None:
    effect = ExternalEffect.model_validate(_valid_effect_payload())
    assert effect.external_reference is None
    assert effect.response_hash is None
    assert effect.reconciliation_method is None
    assert effect.confirmed_at is None


def test_external_effect_rejects_missing_required_field() -> None:
    payload = _valid_effect_payload()
    del payload["request_hash"]
    with pytest.raises(ValidationError):
        ExternalEffect.model_validate(payload)


def test_external_effect_rejects_unknown_fields() -> None:
    payload = _valid_effect_payload()
    payload["extra"] = True
    with pytest.raises(ValidationError):
        ExternalEffect.model_validate(payload)


def test_external_effect_rejects_unknown_status() -> None:
    payload = _valid_effect_payload()
    payload["status"] = "ACTIVE"
    with pytest.raises(ValidationError):
        ExternalEffect.model_validate(payload)


def test_external_effect_rejects_unknown_side_effect_class() -> None:
    payload = _valid_effect_payload()
    payload["side_effect_class"] = "NETWORK_CALL"
    with pytest.raises(ValidationError):
        ExternalEffect.model_validate(payload)
