"""Hash-chained audit ledger."""

from __future__ import annotations

import pytest

from engine.core.errors import DdeError
from tests.support.harness import build_harness


def test_audit_chain_verifies() -> None:
    harness = build_harness()
    first = harness.audit.append(
        tenant_id=harness.tenant_id,
        project_id=harness.project_id,
        event_type="edr.accepted",
        payload={"slug": "EDR-031"},
    )
    second = harness.audit.append(
        tenant_id=harness.tenant_id,
        project_id=harness.project_id,
        event_type="requirement.approved",
        payload={"slug": "REQ-AP-019"},
    )
    assert first.prev_hash is None
    assert second.prev_hash == first.entry_hash
    harness.audit.verify_chain(harness.tenant_id)


def test_tampered_payload_breaks_chain() -> None:
    harness = build_harness()
    entry = harness.audit.append(
        tenant_id=harness.tenant_id,
        project_id=harness.project_id,
        event_type="edr.accepted",
        payload={"slug": "EDR-031"},
    )
    harness.audit._store.entries[entry.audit_event_id] = entry.model_copy(
        update={"payload": {"slug": "forged"}}
    )
    with pytest.raises(DdeError) as captured:
        harness.audit.verify_chain(harness.tenant_id)
    assert captured.value.error_code == "POLICY_DENIED"
