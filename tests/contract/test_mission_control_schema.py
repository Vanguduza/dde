"""Schema tests for the MissionControl projection contract (DDE-028, Ch.15.4)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from engine.contracts.mission_control import MissionControl
from engine.core.ids import uuid7


def _valid_payload() -> dict[str, object]:
    return {
        "mission_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "slug": "MISSION-CTL-1",
        "title": "Mission control",
        "status": "ACTIVE",
        "autonomy_ceiling": 2,
        "lock_version": 1,
        "task_total": 3,
        "task_counts": {"COMPLETED": 2, "EXECUTING": 1},
        "tasks_completed": 2,
        "open_attention_items": 1,
        "attention_debt": 0,
        "human_minutes": 12.5,
        "approvals_per_mission": 1,
        "approvals_by_type": {"architecture_change": 1},
        "blocked_requests": 0,
        "standing_approval_usage": 0,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }


def test_mission_control_is_valid_with_required_fields() -> None:
    projection = MissionControl.model_validate(_valid_payload())
    assert projection.last_event_at is None
    assert projection.task_counts == {"COMPLETED": 2, "EXECUTING": 1}


def test_mission_control_accepts_last_event_at() -> None:
    payload = _valid_payload()
    payload["last_event_at"] = datetime.now(UTC).isoformat()
    projection = MissionControl.model_validate(payload)
    assert projection.last_event_at is not None


def test_mission_control_rejects_unknown_fields() -> None:
    payload = _valid_payload()
    payload["extra"] = True
    with pytest.raises(ValidationError):
        MissionControl.model_validate(payload)


def test_mission_control_requires_task_counts() -> None:
    payload = _valid_payload()
    del payload["task_counts"]
    with pytest.raises(ValidationError):
        MissionControl.model_validate(payload)


def test_mission_control_rejects_unknown_status() -> None:
    payload = _valid_payload()
    payload["status"] = "RUNNING"
    with pytest.raises(ValidationError):
        MissionControl.model_validate(payload)
