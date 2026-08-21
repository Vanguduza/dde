"""Schema tests (Chapter 19.1) for the objects DDE-026 introduces."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from engine.contracts.approval import Approval
from engine.contracts.attention_item import AttentionItem
from engine.contracts.standing_approval import StandingApproval
from engine.core.ids import uuid7


def _now() -> datetime:
    return datetime.now(UTC)


def test_approval_is_valid_with_required_fields() -> None:
    now = _now()
    record = Approval.model_validate(
        {
            "approval_id": uuid7(),
            "tenant_id": uuid7(),
            "project_id": uuid7(),
            "mission_id": uuid7(),
            "approval_type": "architecture_change",
            "scope_hash": "a" * 64,
            "requested_by": uuid7(),
            "required_role": "approval.decide",
            "evidence_refs": [],
            "status": "REQUESTED",
            "human_minutes": 0,
            "command_id": uuid7(),
            "created_at": now,
            "updated_at": now,
        }
    )
    assert record.status == "REQUESTED"
    assert record.task_id is None


def test_approval_rejects_unknown_fields() -> None:
    now = _now()
    with pytest.raises(ValidationError):
        Approval.model_validate(
            {
                "approval_id": uuid7(),
                "tenant_id": uuid7(),
                "project_id": uuid7(),
                "mission_id": uuid7(),
                "approval_type": "architecture_change",
                "scope_hash": "a" * 64,
                "requested_by": uuid7(),
                "required_role": "approval.decide",
                "evidence_refs": [],
                "status": "REQUESTED",
                "human_minutes": 0,
                "command_id": uuid7(),
                "created_at": now,
                "updated_at": now,
                "reusable": True,
            }
        )


def test_standing_approval_is_valid_with_required_fields() -> None:
    now = _now()
    record = StandingApproval.model_validate(
        {
            "standing_id": uuid7(),
            "tenant_id": uuid7(),
            "project_id": uuid7(),
            "approval_types": ["oracle_approval"],
            "blast_radius_ceiling": "module",
            "risk_ceiling": "medium",
            "cost_ceiling": 10.0,
            "task_count_ceiling": 8,
            "path_scope": ["engine"],
            "forbidden_operations": ["IRREVERSIBLE"],
            "valid_from": now,
            "valid_until": now,
            "revocable_immediately": True,
            "granted_by": uuid7(),
            "rationale": "overnight",
            "status": "ACTIVE",
            "task_count_used": 0,
            "cost_used": 0,
            "command_id": uuid7(),
            "created_at": now,
            "updated_at": now,
        }
    )
    assert record.mission_id is None
    assert record.revocable_immediately is True


def test_attention_item_is_valid_with_required_fields() -> None:
    now = _now()
    record = AttentionItem.model_validate(
        {
            "attention_id": uuid7(),
            "tenant_id": uuid7(),
            "project_id": uuid7(),
            "mission_id": uuid7(),
            "kind": "expired_approval",
            "summary": "approval expired",
            "status": "OPEN",
            "sla_due_at": now,
            "opened_at": now,
            "created_at": now,
            "updated_at": now,
        }
    )
    assert record.status == "OPEN"
