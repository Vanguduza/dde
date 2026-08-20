"""Schema tests (Chapter 19.1) for the object DDE-023 introduces:
`Checkpoint` (`engine.recovery`).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from engine.contracts.checkpoint import Checkpoint
from engine.core.ids import uuid7


def _now() -> datetime:
    return datetime.now(UTC)


def _valid_checkpoint_payload() -> dict[str, object]:
    now = _now()
    return {
        "checkpoint_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "mission_id": uuid7(),
        "task_id": uuid7(),
        "task_attempt_id": uuid7(),
        "worker_run_id": uuid7(),
        "context_package_id": uuid7(),
        "execution_plan_id": uuid7(),
        "completed_work": [],
        "verified_work": [],
        "pending_work": ["task"],
        "known_failures": [],
        "next_action": "resume",
        "do_not_repeat": [],
        "artifact_refs": [],
        "lease_refs": [],
        "workspace_revision": "deadbeef",
        "integration_state": "",
        "event_sequence": 1,
        "integrity_hash": "a" * 64,
        "command_id": uuid7(),
        "created_at": now,
        "updated_at": now,
    }


def test_checkpoint_is_valid_with_required_fields() -> None:
    checkpoint = Checkpoint.model_validate(_valid_checkpoint_payload())
    assert checkpoint.do_not_repeat == []
    assert checkpoint.next_action == "resume"


def test_checkpoint_rejects_missing_required_field() -> None:
    payload = _valid_checkpoint_payload()
    del payload["integrity_hash"]
    with pytest.raises(ValidationError):
        Checkpoint.model_validate(payload)


def test_checkpoint_rejects_unknown_fields() -> None:
    payload = _valid_checkpoint_payload()
    payload["progress_percent"] = 50
    with pytest.raises(ValidationError):
        Checkpoint.model_validate(payload)
