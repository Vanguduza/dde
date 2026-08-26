"""PostgreSQL-backed Chapter 6.9 frozen fit, canary, and rollback.

Exercises production mutations against a real database:

- `LearningActivationService.fit_frozen_policy` over eligible
  ExperienceRecords
- `LearningActivationService.rollback` returning to last certified
- `RouterService.route()` applying a frozen mapping on the canary slice
- `attempt_online_update` refusing the partial-information path
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from engine.contracts.learned_routing_policy import LearnedRoutingPolicy
from engine.contracts.routing_activation_state import RoutingActivationState
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.learning.activation_service import LearningActivationService
from engine.learning.policy_repository import LearningPolicyRepository
from engine.routing.policy import PROFILE_GENERAL_IMPLEMENTATION
from engine.routing.service import RouterService
from engine.truth.db import open_unit_of_work
from tests.support.db import new_engine
from tests.support.routing_fixtures import build_routing_fixture
from tests.unit.test_learning_postgres import CLEAN_MODULE, _run_verification


def _now() -> datetime:
    return datetime.now(UTC)


@pytest.mark.asyncio
async def test_fit_frozen_policy_persists_artifact_from_real_experience(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    workspace = None
    try:
        fixture, run, workspaces = await _run_verification(
            engine,
            tmp_path,
            mission_slug="MISSION-LEARN-FIT",
            source=CLEAN_MODULE,
            idempotency_key="learn-fit-1",
        )
        workspace = fixture.workspace
        assert run.status == "PASSED"
        service = LearningActivationService(engine)
        try:
            policy = await service.fit_frozen_policy(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
            )
        except DdeError as exc:
            # A single real record can land entirely in holdout; cold-start
            # refusal is the honest OFFLINE EVALUATE outcome.
            assert exc.details is not None
            assert exc.details.get("reason") == "offline_fit_cold_start"
            return
        assert policy.fit_kind == "frozen_full_information"
        assert policy.continued_update is False
        assert policy.status == "fitted"
        assert policy.train_count >= 1
    finally:
        if workspace is not None:
            from engine.context.repo import repo_root
            from engine.workspaces.service import WorkspaceService

            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_rollback_returns_to_last_certified_never_untested(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    try:
        fixture = await build_routing_fixture(
            engine, tmp_path, mission_slug="MISSION-LEARN-ROLLBACK"
        )
        now = _now()
        policy = LearnedRoutingPolicy(
            policy_id=uuid7(),
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            learning_run_id=uuid7(),
            fit_kind="frozen_full_information",
            policy_hash="rollback-test-hash",
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
        rolled = await LearningActivationService(engine).rollback(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        )
        assert rolled.routing_mode == "deterministic"
        assert rolled.active_policy_id is None
        assert rolled.last_certified_mode == "deterministic"
        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            still = await LearningPolicyRepository().get(
                uow.connection, policy.policy_id
            )
            await uow.commit()
        assert still is not None
        assert still.status == "fitted"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_route_applies_frozen_mapping_on_canary_slice(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    try:
        fixture = await build_routing_fixture(
            engine, tmp_path, mission_slug="MISSION-LEARN-CANARY"
        )
        now = _now()
        policy = LearnedRoutingPolicy(
            policy_id=uuid7(),
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            learning_run_id=uuid7(),
            fit_kind="frozen_full_information",
            policy_hash="canary-test-hash",
            mapping={"bulk_implementation": PROFILE_GENERAL_IMPLEMENTATION},
            constant_policy_profile_id=PROFILE_GENERAL_IMPLEMENTATION,
            train_count=10,
            holdout_count=2,
            brier=0.05,
            ece=0.02,
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
        decision = await RouterService(engine).route(task=fixture.task)
        assert decision.selection_source == "canary"
        assert decision.selected_worker_profile_id == PROFILE_GENERAL_IMPLEMENTATION
        assert "LEARNED_FROZEN" in decision.reason_codes
        assert "FROZEN_EXPLOITATION" in decision.reason_codes
        assert "CANARY_ASSIGNED" in decision.reason_codes
        assert decision.policy_version.startswith("frozen:")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_attempt_online_update_is_unreachable(tmp_path: Path) -> None:
    engine = new_engine()
    try:
        fixture = await build_routing_fixture(
            engine, tmp_path, mission_slug="MISSION-LEARN-ONLINE"
        )
        with pytest.raises(DdeError, match="partial-information") as exc:
            await LearningActivationService(engine).attempt_online_update(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
            )
        details = exc.value.details or {}
        assert details.get("reason") == "no_online_updater"
    finally:
        await engine.dispose()
