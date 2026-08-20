"""Mission Kernel state machine."""

from __future__ import annotations

import pytest

from engine.core.errors import DdeError
from tests.support.harness import CONSTITUTION, build_harness


def _mission(harness, intent: str = "Add a /health endpoint"):
    harness.truth.publish_constitution(
        tenant_id=harness.tenant_id,
        project_id=harness.project_id,
        body_markdown=CONSTITUTION,
    )
    requirement = harness.truth.draft_requirement(
        tenant_id=harness.tenant_id,
        project_id=harness.project_id,
        slug="REQ-HEALTH",
        statement="Health endpoint reports liveness",
        constraints=[],
        acceptance_conditions=["GET /healthz returns ok"],
    )
    harness.truth.approve_requirement(requirement.requirement_id)
    return harness.missions.commit_mission(
        tenant_id=harness.tenant_id,
        project_id=harness.project_id,
        slug="MISSION-HEALTH-1",
        title="Health endpoint",
        intent=intent,
        success_definition="healthz returns ok",
        scope=["engine", "schemas", "tests"],
        requirement_refs=["REQ-HEALTH"],
        autonomy_ceiling=3,
    )


def test_mission_created_to_active_to_completed() -> None:
    harness = build_harness()
    mission = _mission(harness)
    started = harness.missions.start(
        mission.mission_id, lock_version=mission.lock_version
    )
    assert started.status == "ACTIVE"
    completed = harness.missions.complete(
        started.mission_id, lock_version=started.lock_version
    )
    assert completed.status == "COMPLETED"


def test_stale_lock_version_conflicts() -> None:
    harness = build_harness()
    mission = _mission(harness)
    harness.missions.start(mission.mission_id, lock_version=mission.lock_version)
    with pytest.raises(DdeError) as captured:
        harness.missions.pause(mission.mission_id, lock_version=mission.lock_version)
    assert captured.value.error_code == "VERSION_CONFLICT"


def test_illegal_terminal_resume() -> None:
    harness = build_harness()
    mission = _mission(harness)
    started = harness.missions.start(
        mission.mission_id, lock_version=mission.lock_version
    )
    cancelled = harness.missions.cancel(
        started.mission_id, lock_version=started.lock_version
    )
    with pytest.raises(DdeError):
        harness.missions.resume(
            cancelled.mission_id, lock_version=cancelled.lock_version
        )


def test_pause_resume() -> None:
    harness = build_harness()
    mission = _mission(harness)
    started = harness.missions.start(
        mission.mission_id, lock_version=mission.lock_version
    )
    paused = harness.missions.pause(
        started.mission_id, lock_version=started.lock_version
    )
    resumed = harness.missions.resume(
        paused.mission_id, lock_version=paused.lock_version
    )
    assert paused.status == "PAUSED"
    assert resumed.status == "ACTIVE"
