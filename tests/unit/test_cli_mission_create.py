"""Unit tests for `interfaces.cli.mission_create`'s pure rendering logic
(Chapter 19.1 unit test type) -- hand-built `Mission` values, no database,
mirroring `tests/unit/test_cli_mission_trace.py`'s pattern for its own
pure-logic module.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from engine.contracts.mission import Mission
from interfaces.cli.mission_create import render_created_mission

NOW = datetime.now(UTC)


def _mission() -> Mission:
    return Mission(
        mission_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        slug="mission-create-unit",
        title="Unit test mission",
        intent="Exercise the mission-create renderer",
        success_definition="dde mission create prints a real mission_id",
        scope=["engine", "tests"],
        requirement_refs=["REQ-1"],
        status="CREATED",
        autonomy_ceiling=2,
        lock_version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def test_render_created_mission_includes_every_real_field() -> None:
    mission = _mission()
    output = render_created_mission(mission)

    assert "Mission created" in output
    assert str(mission.mission_id) in output
    assert str(mission.tenant_id) in output
    assert str(mission.project_id) in output
    assert repr(mission.slug) in output
    assert mission.title in output
    assert mission.intent in output
    assert mission.success_definition in output
    assert "REQ-1" in output
    assert f"status: {mission.status}" in output
    assert f"autonomy_ceiling: {mission.autonomy_ceiling}" in output
    assert f"lock_version: {mission.lock_version}" in output
