"""Flight Lab golden mission + S7 scenarios (Ch.19.2).

Exercises production call sites, not helpers:

- spine: `build_golden_mission` → MissionService / RouterService /
  IntegrationQueueService (same path `just check` already runs)
- worker outage: `RouterService.route` with preferred profiles REVOKED
- policy rollback: `LearningActivationService.rollback` then `route()`
  uses the last certified (deterministic) policy
- workspace escape / credential-path: `WorkspaceService.read`
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from engine.context.repo import repo_root
from engine.contracts.learned_routing_policy import LearnedRoutingPolicy
from engine.contracts.routing_activation_state import RoutingActivationState
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.integration import git
from engine.learning.activation_service import LearningActivationService
from engine.learning.policy_repository import LearningPolicyRepository
from engine.routing.policy import (
    HUMAN_DECISION_TASK,
    PROFILE_GENERAL_IMPLEMENTATION,
    WORKLOAD_CLASSES,
)
from engine.routing.repository import RouteDecisionRepository
from engine.routing.service import RouterService
from engine.truth.db import open_unit_of_work
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.golden_mission import (
    GOLDEN_MISSION_SLUG,
    GOLDEN_MISSION_TITLE,
    GOLDEN_REQUIREMENT_SLUG,
    GOLDEN_REQUIREMENT_STATEMENT,
    build_golden_mission,
)
from tests.support.routing_fixtures import build_routing_fixture


def _now() -> datetime:
    return datetime.now(UTC)


async def _cleanup_trace(engine, trace) -> None:
    root = repo_root()
    await WorkspaceService(engine, root=root).cleanup(
        workspace=trace.advanced.workspace
    )
    git.delete_branch(root, trace.task_branch)
    git.delete_branch(root, trace.mission_branch)


@pytest.mark.asyncio
async def test_golden_mission_erp_identity_spine_and_workspace_escape(
    tmp_path: Path,
) -> None:
    """§19.2 identity plus the existing executable spine, then Flight Lab
    attempts workspace escape / credential-path reads as security failures."""
    engine = new_engine()
    trace = None
    try:
        trace = await build_golden_mission(engine, tmp_path)
        assert trace.mission.slug == GOLDEN_MISSION_SLUG
        assert trace.mission.title == GOLDEN_MISSION_TITLE
        assert GOLDEN_REQUIREMENT_SLUG in trace.mission.requirement_refs
        assert trace.proposal.status == "MERGED"
        assert trace.advanced.verification_run.status == "PASSED"
        decision = trace.route_decision
        assert decision.selection_source != "exploration"
        assert float(decision.selection_propensity) == 1.0

        workspace = trace.advanced.workspace
        service = WorkspaceService(engine, root=repo_root())
        with pytest.raises(DdeError) as escape:
            service.read(workspace, "../.env")
        assert escape.value.error_code == "POLICY_DENIED"

        with pytest.raises(DdeError) as absolute:
            service.read(workspace, str(Path.home() / ".ssh" / "id_rsa"))
        assert absolute.value.error_code == "POLICY_DENIED"

        workspace_path = Path(workspace.workspace_path or "")
        assert workspace_path.is_dir()
        outside = workspace_path.parent / "dde-flight-lab-secret.txt"
        outside.write_text("secret", encoding="utf-8")
        try:
            link = workspace_path / "escape-link"
            try:
                link.symlink_to(outside)
            except OSError:
                pytest.skip("symlink creation not permitted in this environment")
            with pytest.raises(DdeError) as symlink_escape:
                service.read(workspace, "escape-link")
            assert symlink_escape.value.error_code == "POLICY_DENIED"
        finally:
            outside.unlink(missing_ok=True)
    finally:
        if trace is not None:
            await _cleanup_trace(engine, trace)
        await engine.dispose()


@pytest.mark.asyncio
async def test_s7_worker_outage_persists_via_router_service(tmp_path: Path) -> None:
    """S7 golden-mission scenario: worker outage at `RouterService.route`,
    not `evaluate()` / the RSM fixture generator."""
    engine = new_engine()
    try:
        fixture = await build_routing_fixture(
            engine,
            tmp_path,
            mission_slug=GOLDEN_MISSION_SLUG,
            mission_title=GOLDEN_MISSION_TITLE,
            requirement_slug=GOLDEN_REQUIREMENT_SLUG,
            requirement_statement=GOLDEN_REQUIREMENT_STATEMENT,
            task_class="implementation",
        )
        revoked = {
            profile_id: "REVOKED"
            for profile_id in WORKLOAD_CLASSES["bulk_implementation"].prefer
        }
        decision = await RouterService(engine).route(
            task=fixture.task,
            certification_statuses=revoked,
            routing_environment_class="production",
            approval_satisfied=True,
        )
        assert decision.selected_worker_profile_id == HUMAN_DECISION_TASK
        assert "NO_ELIGIBLE_WORKER" in decision.reason_codes
        assert decision.selection_source != "exploration"
        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            reloaded = await RouteDecisionRepository().get_route_decision(
                uow.connection, decision.decision_id
            )
            await uow.commit()
        assert reloaded == decision
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_s7_policy_rollback_then_route_uses_certified_policy(
    tmp_path: Path,
) -> None:
    """S7 golden-mission scenario: `LearningActivationService.rollback`
    is the mutation; subsequent `RouterService.route` is the reader."""
    engine = new_engine()
    try:
        fixture = await build_routing_fixture(
            engine,
            tmp_path,
            mission_slug=GOLDEN_MISSION_SLUG,
            mission_title=GOLDEN_MISSION_TITLE,
            requirement_slug=GOLDEN_REQUIREMENT_SLUG,
            requirement_statement=GOLDEN_REQUIREMENT_STATEMENT,
        )
        now = _now()
        policy = LearnedRoutingPolicy(
            policy_id=uuid7(),
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            learning_run_id=uuid7(),
            fit_kind="frozen_full_information",
            policy_hash="flight-lab-rollback-hash",
            mapping={"bulk_implementation": PROFILE_GENERAL_IMPLEMENTATION},
            constant_policy_profile_id=PROFILE_GENERAL_IMPLEMENTATION,
            train_count=10,
            holdout_count=2,
            brier=0.05,
            ece=0.02,
            holdout_learner_expected=0.9,
            holdout_constant_expected=0.7,
            holdout_incumbent_success=0.8,
            beats_constant_policy=True,
            holdout_regression=False,
            drift_within_bounds=True,
            continued_update=False,
            status="fitted",
            training_experience_ids=[],
            fallback_robustness_demonstrated=True,
            created_at=now,
            updated_at=now,
        )
        state = RoutingActivationState(
            activation_id=uuid7(),
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            routing_mode="canary",
            active_policy_id=policy.policy_id,
            last_certified_policy_id=None,
            last_certified_mode="deterministic",
            canary_fraction=1.0,
            continued_update_enabled=False,
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            repo = LearningPolicyRepository()
            await repo.insert_policy(uow.connection, policy)
            await repo.upsert_activation(uow.connection, state)
            await uow.commit()

        canary = await RouterService(engine).route(task=fixture.task)
        assert canary.selection_source == "canary"
        assert "LEARNED_FROZEN" in canary.reason_codes

        rolled = await LearningActivationService(engine).rollback(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        )
        assert rolled.routing_mode == "deterministic"
        assert rolled.active_policy_id is None

        restored = await RouterService(engine).route(task=fixture.task)
        assert restored.selection_source == "deterministic"
        assert "LEARNED_FROZEN" not in restored.reason_codes
        assert not restored.policy_version.startswith("frozen:")
        assert restored.selection_source != "exploration"
    finally:
        await engine.dispose()
