"""Schema tests (Chapter 19.1) for the object DDE-016 introduces:
`CapabilityDescriptor` (`engine.capabilities`)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from engine.contracts.capability_descriptor import CapabilityDescriptor
from engine.core.ids import uuid7


def _now() -> datetime:
    return datetime.now(UTC)


def _valid_descriptor_payload() -> dict[str, object]:
    return {
        "descriptor_id": uuid7(),
        "capability_id": "capability.run_local_process",
        "version": "1",
        "category": "process",
        "summary": "Execute a command inside a provisioned workspace.",
        "implementations": ["engine.environments.backends.local_process"],
        "supported_worker_profiles": [],
        "supported_environments": [],
        "supported_workloads": ["bulk_implementation"],
        "risk_class": "low",
        "side_effect_class": "WORKSPACE_LOCAL",
        "enforcement_tier": "T1",
        "permission_model": {},
        "cost_model": {},
        "network_requirements": {"egress": "none"},
        "dependencies": [],
        "provenance": {"source": "native"},
        "certification_status": "CERTIFIED",
        "lifecycle_status": "ACTIVE",
        "visibility": "global",
        "descriptor_hash": "abc123",
        "registered_by": "system:test",
        "created_at": _now(),
        "updated_at": _now(),
    }


def test_capability_descriptor_is_valid_with_only_required_fields() -> None:
    descriptor = CapabilityDescriptor.model_validate(_valid_descriptor_payload())
    assert descriptor.interface_schema_ref is None
    assert descriptor.owner_tenant_id is None
    assert descriptor.supersedes_descriptor_id is None


def test_capability_descriptor_rejects_missing_required_field() -> None:
    payload = _valid_descriptor_payload()
    del payload["side_effect_class"]
    with pytest.raises(ValidationError):
        CapabilityDescriptor.model_validate(payload)


def test_capability_descriptor_rejects_unknown_fields() -> None:
    payload = _valid_descriptor_payload()
    payload["extra"] = True
    with pytest.raises(ValidationError):
        CapabilityDescriptor.model_validate(payload)


def test_capability_descriptor_rejects_unknown_side_effect_class() -> None:
    """Chapter 9.3: the taxonomy is a real, closed enum, not free text."""
    payload = _valid_descriptor_payload()
    payload["side_effect_class"] = "SOMETHING_MADE_UP"
    with pytest.raises(ValidationError):
        CapabilityDescriptor.model_validate(payload)


def test_capability_descriptor_rejects_unknown_enforcement_tier() -> None:
    """Chapter 9.1: enforcement_tier is T1 or T2 only (Chapter 7.2) --
    `audit_only` belongs to `ExecutionPlan`, never to a capability's own
    declared descriptor."""
    payload = _valid_descriptor_payload()
    payload["enforcement_tier"] = "audit_only"
    with pytest.raises(ValidationError):
        CapabilityDescriptor.model_validate(payload)


def test_capability_descriptor_rejects_unknown_lifecycle_status() -> None:
    payload = _valid_descriptor_payload()
    payload["lifecycle_status"] = "ARCHIVED"
    with pytest.raises(ValidationError):
        CapabilityDescriptor.model_validate(payload)


def test_capability_descriptor_rejects_unknown_visibility() -> None:
    payload = _valid_descriptor_payload()
    payload["visibility"] = "public"
    with pytest.raises(ValidationError):
        CapabilityDescriptor.model_validate(payload)
