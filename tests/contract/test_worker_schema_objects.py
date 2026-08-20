"""Schema tests (Chapter 19.1) for the objects DDE-011 introduces:
`WorkerRun`, `WorkerEvent` (`engine.workers`) and `TaskAttempt`
(`engine.missions`)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from engine.contracts.task_attempt import TaskAttempt
from engine.contracts.worker_event import WorkerEvent
from engine.contracts.worker_run import WorkerRun
from engine.core.ids import uuid7


def _now() -> datetime:
    return datetime.now(UTC)


def _valid_worker_run_payload() -> dict[str, object]:
    return {
        "run_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "mission_id": uuid7(),
        "task_attempt_id": uuid7(),
        "sequence": 1,
        "execution_plan_id": uuid7(),
        "worker_id": "worker.scripted-deterministic-v1",
        "worker_profile_id": "profile.deterministic_runner",
        "environment_id": uuid7(),
        "workspace_id": uuid7(),
        "context_package_id": uuid7(),
        "policy_version": "worker-manager-v1",
        "lease_set_hash": "abc123",
        "status": "PLANNED",
        "created_at": _now(),
        "updated_at": _now(),
    }


def test_worker_run_is_valid_with_only_required_fields() -> None:
    run = WorkerRun.model_validate(_valid_worker_run_payload())
    assert run.worker_session_id is None
    assert run.failure_class is None
    assert run.checkpoint_id is None
    assert run.usage_record_id is None
    assert run.artifact_manifest_id is None
    assert run.started_at is None
    assert run.ended_at is None


def test_worker_run_rejects_missing_required_field() -> None:
    payload = _valid_worker_run_payload()
    del payload["lease_set_hash"]
    with pytest.raises(ValidationError):
        WorkerRun.model_validate(payload)


def test_worker_run_rejects_unknown_fields() -> None:
    payload = _valid_worker_run_payload()
    payload["extra"] = True
    with pytest.raises(ValidationError):
        WorkerRun.model_validate(payload)


def _valid_worker_event_payload() -> dict[str, object]:
    return {
        "event_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "mission_id": uuid7(),
        "run_id": uuid7(),
        "task_id": uuid7(),
        "sequence": 1,
        "event_type": "WorkerRunCreated",
        "occurred_at": _now(),
        "actor": "worker_manager",
        "correlation_id": str(uuid7()),
        "payload": {"worker_id": "worker.scripted-deterministic-v1"},
        "schema_version": "1",
        "integrity_hash": "abc123",
        "created_at": _now(),
        "updated_at": _now(),
    }


def test_worker_event_is_valid_with_only_required_fields() -> None:
    event = WorkerEvent.model_validate(_valid_worker_event_payload())
    assert event.causation_id is None


def test_worker_event_rejects_missing_required_field() -> None:
    payload = _valid_worker_event_payload()
    del payload["integrity_hash"]
    with pytest.raises(ValidationError):
        WorkerEvent.model_validate(payload)


def test_worker_event_rejects_unknown_fields() -> None:
    payload = _valid_worker_event_payload()
    payload["extra"] = True
    with pytest.raises(ValidationError):
        WorkerEvent.model_validate(payload)


def _valid_task_attempt_payload() -> dict[str, object]:
    return {
        "attempt_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "mission_id": uuid7(),
        "task_id": uuid7(),
        "sequence": 1,
        "execution_plan_id": uuid7(),
        "input_context_hash": "abc123",
        "workspace_revision": "deadbeef",
        "result_artifact_refs": [],
        "verification_refs": [],
        "status": "IN_PROGRESS",
        "created_at": _now(),
        "updated_at": _now(),
    }


def test_task_attempt_is_valid_with_only_required_fields() -> None:
    attempt = TaskAttempt.model_validate(_valid_task_attempt_payload())
    assert attempt.integration_proposal_id is None
    assert attempt.failure_class is None
    assert attempt.retry_of is None
    assert attempt.checkpoint_id is None
    assert attempt.started_at is None
    assert attempt.ended_at is None


def test_task_attempt_rejects_missing_required_field() -> None:
    payload = _valid_task_attempt_payload()
    del payload["workspace_revision"]
    with pytest.raises(ValidationError):
        TaskAttempt.model_validate(payload)


def test_task_attempt_rejects_unknown_fields() -> None:
    payload = _valid_task_attempt_payload()
    payload["extra"] = True
    with pytest.raises(ValidationError):
        TaskAttempt.model_validate(payload)
