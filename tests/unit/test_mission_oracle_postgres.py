"""Chapter 11.3 mission-level AcceptanceOracle + wrong-product detection
(DDE-037).

Contract: a planted wrong-product implementation -- every task oracle
PASSED, the mission oracle itself FAILED -- must persist as
WRONG_PRODUCT, a decomposition-quality learning signal, never a worker
failure and never a silent skip. Medium-or-higher missions cannot
COMPLETE without an ACCEPT mission-oracle evaluation.
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

from engine.context.repo import repo_root
from engine.core.errors import DdeError
from engine.events.service import EventService
from engine.missions.service import MissionService
from engine.verification.checks import CheckSpec
from engine.verification.mission_oracle import MissionOracleService
from engine.verification.oracle import AcceptanceOracleService
from engine.verification.runner import VerificationRunnerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.routing_fixtures import build_routing_fixture
from tests.support.verification_fixtures import build_verification_fixture


def _passing_spec(statement: str) -> CheckSpec:
    return CheckSpec(
        outcome_id=uuid4(),
        statement=statement,
        kind="test",
        ref="tests/unit/test_task_oracle.py::test_unit",
        command=[sys.executable, "-c", "raise SystemExit(0)"],
    )


def _failing_spec(statement: str) -> CheckSpec:
    return CheckSpec(
        outcome_id=uuid4(),
        statement=statement,
        kind="test",
        ref="tests/e2e/test_user_visible_product.py::test_right_product",
        command=[sys.executable, "-c", "raise SystemExit(1)"],
    )


@pytest.mark.asyncio
async def test_planted_wrong_product_is_classified_not_worker_failure(
    tmp_path: Path,
) -> None:
    """S4 exit gate / Chapter 11.3: mission oracle rejects a planted
    wrong-product implementation whose code-level (task) tests all pass."""
    engine = new_engine()
    root = repo_root()
    workspace_root = tmp_path / "ws"
    workspace = None
    try:
        fixture = await build_verification_fixture(
            engine, workspace_root, mission_slug="MISSION-037-WRONG-PRODUCT"
        )
        workspace = fixture.workspace
        oracles = AcceptanceOracleService(engine)
        task_oracle = await oracles.define(
            task=fixture.task, outcomes=[_passing_spec("unit behaviour holds")]
        )
        runner = VerificationRunnerService(engine, WorkspaceService(engine, root=root))
        task_run = await runner.run(
            task=fixture.task,
            worker_run=fixture.worker_run,
            workspace=fixture.workspace,
            oracle=task_oracle,
            idempotency_key="dde-037-task-oracle-pass",
        )
        assert task_run.status == "PASSED"

        mission_oracle = await oracles.define_mission(
            mission=fixture.mission,
            outcomes=[
                _failing_spec(
                    "user-visible product behaviour holds on the mission branch"
                )
            ],
        )
        assert mission_oracle.scope == "mission"
        assert mission_oracle.task_id is None

        service = MissionOracleService(engine, WorkspaceService(engine, root=root))
        evaluation = await service.evaluate(
            mission=fixture.mission,
            workspace=fixture.workspace,
            idempotency_key="dde-037-wrong-product-1",
        )
        assert evaluation.status == "WRONG_PRODUCT"
        assert evaluation.task_oracle_verdict == "all_passed"
        assert evaluation.learning_signal_class == "decomposition_quality"
        assert evaluation.excluded_from_routing_learning is True
        assert evaluation.recovery_decision is not None
        assert evaluation.recovery_decision["failure_class"] == "WRONG_PRODUCT"
        assert evaluation.recovery_decision["requires_replan"] is True
        assert evaluation.recovery_decision["allow_new_worker_run"] is False

        replayed = await service.evaluate(
            mission=fixture.mission,
            workspace=fixture.workspace,
            idempotency_key="dde-037-wrong-product-1",
        )
        assert replayed.evaluation_id == evaluation.evaluation_id

        missions = MissionService(engine, EventService(engine))
        active = await missions.transition_mission(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.mission.mission_id,
            target_status="ACTIVE",
            lock_version=fixture.mission.lock_version,
        )
        with pytest.raises(DdeError) as captured:
            await missions.transition_mission(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                mission_id=fixture.mission.mission_id,
                target_status="COMPLETED",
                lock_version=active.lock_version,
            )
        assert captured.value.error_code in {"ORACLE_UNSATISFIED", "WRONG_PRODUCT"}
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=root).cleanup(workspace=workspace)
        await engine.dispose()


@pytest.mark.asyncio
async def test_medium_risk_mission_cannot_complete_without_mission_oracle(
    tmp_path: Path,
) -> None:
    """Chapter 11.3: every mission with risk >= medium carries a mission
    oracle; COMPLETED without one is refused."""
    engine = new_engine()
    try:
        fixture = await build_routing_fixture(
            engine,
            tmp_path,
            mission_slug="MISSION-037-MEDIUM-RISK",
            risk_class="medium",
        )
        missions = MissionService(engine, EventService(engine))
        active = await missions.transition_mission(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.mission.mission_id,
            target_status="ACTIVE",
            lock_version=fixture.mission.lock_version,
        )
        with pytest.raises(DdeError) as captured:
            await missions.transition_mission(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                mission_id=fixture.mission.mission_id,
                target_status="COMPLETED",
                lock_version=active.lock_version,
            )
        assert captured.value.error_code == "ORACLE_UNSATISFIED"
    finally:
        await engine.dispose()
