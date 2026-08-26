"""PostgreSQL-backed Chapter 5.13 context-policy activation.

Exercises production mutations against a real database:

- `ContextActivationService.attempt_advance` refuses canary without a
  full Chapter 5.13 pass
- shadow advance is allowed (observation only)
- rollback returns to last certified (Stage 1 pull)
- `ContextService.compile()` is the production reader of canary state
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from engine.context.activation_repository import ContextActivationRepository
from engine.context.activation_service import ContextActivationService
from engine.context.index_service import ContextIndexService
from engine.context.model import ContextBudgetExceeded
from engine.context.service import ContextService
from engine.contracts.context_activation_state import ContextActivationState
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.truth.db import open_unit_of_work
from tests.support.context_fixtures import build_context_fixture, build_fake_repo
from tests.support.db import new_engine


def _now() -> datetime:
    return datetime.now(UTC)


@pytest.mark.asyncio
async def test_attempt_advance_refuses_canary_without_full_gates(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    try:
        build_fake_repo(tmp_path)
        fixture = await build_context_fixture(
            engine, mission_slug="MISSION-CTX-ACT-CANARY"
        )
        service = ContextActivationService(engine)
        with pytest.raises(DdeError) as exc_info:
            await service.attempt_advance(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                requested_mode="canary",
                candidate_arm="semantic",
            )
        assert exc_info.value.error_code == "POLICY_DENIED"
        assert exc_info.value.details is not None
        reasons = exc_info.value.details["refused_reasons"]
        assert "illegal_mode_transition" in reasons
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_shadow_advance_persists_and_compile_stays_pull(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    try:
        build_fake_repo(tmp_path)
        fixture = await build_context_fixture(
            engine, mission_slug="MISSION-CTX-ACT-SHADOW"
        )
        index_service = ContextIndexService(engine, root=tmp_path)
        await index_service.build_index(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        )
        activation = ContextActivationService(engine)
        verdict = await activation.attempt_advance(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            requested_mode="shadow",
            candidate_arm="semantic",
        )
        assert verdict.allowed
        service = ContextService(engine, root=tmp_path, index_service=index_service)
        compiled = await service.compile(task=fixture.task)
        assert not isinstance(compiled, ContextBudgetExceeded)
        assert "semantic" not in compiled.retrievers_used
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_rollback_from_seeded_canary_restores_certified_pull(
    tmp_path: Path,
) -> None:
    """compile() honors a canary row (as a future PASS would write) and
    rollback returns to last certified pull. attempt_advance cannot
    itself write canary while EDR-0003 replay gates remain deferred."""
    engine = new_engine()
    try:
        build_fake_repo(tmp_path)
        fixture = await build_context_fixture(
            engine, mission_slug="MISSION-CTX-ACT-ROLLBACK"
        )
        index_service = ContextIndexService(engine, root=tmp_path)
        await index_service.build_index(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        )
        now = _now()
        seeded = ContextActivationState(
            activation_id=uuid7(),
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            context_mode="canary",
            candidate_arm="semantic",
            last_certified_mode="certified_baseline",
            last_certified_arm="pull",
            last_promotion_run_id=None,
            canary_fraction=1.0,
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            await ContextActivationRepository().upsert(uow.connection, seeded)
            await uow.commit()

        service = ContextService(engine, root=tmp_path, index_service=index_service)
        canary_compiled = await service.compile(task=fixture.task)
        assert not isinstance(canary_compiled, ContextBudgetExceeded)
        assert "semantic" in canary_compiled.retrievers_used

        rolled = await ContextActivationService(engine).rollback(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        )
        assert rolled.context_mode == "certified_baseline"
        assert rolled.candidate_arm == "pull"

        restored = await service.compile(task=fixture.task)
        assert not isinstance(restored, ContextBudgetExceeded)
        assert "semantic" not in restored.retrievers_used
    finally:
        await engine.dispose()
