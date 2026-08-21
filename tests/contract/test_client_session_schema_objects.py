"""Schema tests (Chapter 19.1) for the ClientSession object (DDE-027)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from engine.contracts.client_session import ClientSession
from engine.core.ids import uuid7


def _now() -> datetime:
    return datetime.now(UTC)


def _valid() -> dict[str, object]:
    now = _now()
    return {
        "session_id": uuid7(),
        "tenant_id": uuid7(),
        "principal_id": uuid7(),
        "client_type": "human",
        "protocol_version": "1",
        "scopes": ["mission.read"],
        "connected_at": now,
        "last_seen_at": now,
        "subscriptions": ["mission"],
        "status": "ACTIVE",
        "created_at": now,
        "updated_at": now,
    }


def test_client_session_is_valid_with_required_fields() -> None:
    record = ClientSession.model_validate(_valid())
    assert record.status == "ACTIVE"
    assert record.device_id is None
    assert record.scopes == ["mission.read"]


def test_client_session_accepts_device_id_and_subscriptions() -> None:
    payload = _valid()
    payload["device_id"] = uuid7()
    payload["subscriptions"] = ["mission", "worker_run"]
    record = ClientSession.model_validate(payload)
    assert record.device_id is not None
    assert record.subscriptions == ["mission", "worker_run"]


def test_client_session_rejects_unknown_fields() -> None:
    payload = _valid()
    payload["extra_field"] = "nope"
    with pytest.raises(ValidationError):
        ClientSession.model_validate(payload)


def test_client_session_requires_tenant_id() -> None:
    payload = _valid()
    del payload["tenant_id"]
    with pytest.raises(ValidationError):
        ClientSession.model_validate(payload)


def test_client_session_requires_scopes() -> None:
    payload = _valid()
    del payload["scopes"]
    with pytest.raises(ValidationError):
        ClientSession.model_validate(payload)
