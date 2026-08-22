"""PostgreSQL-backed Chapter 5.11 failure-attribution engine (Chapter
19.1). Exercises the real production mutation call site --
`engine.verification.runner.VerificationRunnerService.run()`'s `FAILED`
branch calling `engine.attribution.service.FailureAttributionService.
attribute_verification_failure()` inside the same transaction as the
`FAILED` `VerificationRun` and `TaskAttempt` rows -- against a real
database, not a fixture double.
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

from engine.attribution.repository import FailureAttributionRepository
from engine.attribution.rules import CONTEXT_REQUEST_RULE_DEFERRED
from engine.attribution.service import FailureAttributionService
from engine.context.repo import repo_root
from engine.events.repository import EventsRepository
from engine.truth.db import open_unit_of_work
from engine.verification.checks import CheckSpec
from engine.verification.oracle import AcceptanceOracleService
from engine.verification.runner import VerificationRunnerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.verification_fixtures import build_verification_fixture

LINT_BROKEN_MODULE = """import os


def unused_import() -> None:
    return None
"""


@pytest.mark.asyncio
async def test_failed_verification_run_persists_a_rule_based_attribution(
    tmp_path: Path,
) -> None:
    """The real call site: a genuinely FAILED `VerificationRun` (a real
    broken `ruff check`, same fixture shape as `engine.verification`'s own
    FAILED-verdict proof) leaves behind exactly one durable
    `FailureAttribution` row, linked to the same run and attempt, decided
    by the deterministic rule set -- never a model call, never silently
    skipped."""
    root = repo_root()
    db_engine = new_engine()
    workspace = None
    try:
        fixture = await build_verification_fixture(
            db_engine, tmp_path, mission_slug="MISSION-ATTRIBUTION-FAIL"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(db_engine, root=root)
        workspaces.write(
            workspace, "verification_check.py", LINT_BROKEN_MODULE.encode()
        )

        lint_outcome = CheckSpec(
            outcome_id=uuid4(),
            statement="ruff check reports no lint violations on verification_check.py",
            kind="test",
            ref="ruff:verification_check.py",
            command=[sys.executable, "-m", "ruff", "check", "verification_check.py"],
        )
        oracles = AcceptanceOracleService(db_engine)
        oracle = await oracles.define(
            task=fixture.task, outcomes=[lint_outcome], minimum_confidence=1.0
        )

        runner = VerificationRunnerService(db_engine, workspaces)
        run = await runner.run(
            task=fixture.task,
            worker_run=fixture.worker_run,
            workspace=fixture.workspace,
            oracle=oracle,
            idempotency_key="attribution-run-fail-1",
        )
        assert run.status == "FAILED"

        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            attribution = await FailureAttributionRepository().get_by_verification_run(
                uow.connection, run.verification_run_id
            )
            events = await EventsRepository().list_events_for_aggregate(
                uow.connection,
                "failure_attribution",
                attribution.attribution_id if attribution else uuid4(),
            )
            await uow.commit()

        assert attribution is not None
        assert attribution.verification_run_id == run.verification_run_id
        assert attribution.task_id == fixture.task.task_id
        assert attribution.task_attempt_id == fixture.worker_run.task_attempt_id
        assert attribution.mission_id == fixture.mission.mission_id
        assert attribution.method == "rule_based"
        assert attribution.outcome in (
            "context_attributed",
            "not_context_attributed",
            "inconclusive",
        )
        assert CONTEXT_REQUEST_RULE_DEFERRED in attribution.rule_reasons
        if attribution.outcome == "inconclusive":
            assert attribution.eligible_for_promotion_gating is False
        else:
            assert attribution.eligible_for_promotion_gating is True
        assert attribution.excluded_from_routing_learning == (
            attribution.outcome == "context_attributed"
        )
        assert [event.event_type for event in events] == ["FailureAttributionRecorded"]
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(workspace=workspace)
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_attribution_is_idempotent_on_verification_run(tmp_path: Path) -> None:
    """AGENTS.md idempotency rule, enforced atomically (Chapter 5.11): a
    second `attribute_verification_failure()` call for the same, already
    real, persisted `VerificationRun` returns the first call's row rather
    than racing a duplicate insert against the real `UNIQUE
    (verification_run_id)` constraint."""
    root = repo_root()
    db_engine = new_engine()
    workspace = None
    try:
        fixture = await build_verification_fixture(
            db_engine, tmp_path, mission_slug="MISSION-ATTRIBUTION-IDEMPOTENT"
        )
        workspace = fixture.workspace
        workspaces = WorkspaceService(db_engine, root=root)
        workspaces.write(
            workspace, "verification_check.py", LINT_BROKEN_MODULE.encode()
        )
        lint_outcome = CheckSpec(
            outcome_id=uuid4(),
            statement="ruff check reports no lint violations on verification_check.py",
            kind="test",
            ref="ruff:verification_check.py",
            command=[sys.executable, "-m", "ruff", "check", "verification_check.py"],
        )
        oracles = AcceptanceOracleService(db_engine)
        oracle = await oracles.define(
            task=fixture.task, outcomes=[lint_outcome], minimum_confidence=1.0
        )
        runner = VerificationRunnerService(db_engine, workspaces)
        run = await runner.run(
            task=fixture.task,
            worker_run=fixture.worker_run,
            workspace=fixture.workspace,
            oracle=oracle,
            idempotency_key="attribution-run-idempotent-1",
        )
        assert run.status == "FAILED"

        attribution_service = FailureAttributionService(db_engine)
        first = await attribution_service.attribute_verification_failure(
            task=fixture.task,
            task_attempt_id=fixture.worker_run.task_attempt_id,
            verification_run_id=run.verification_run_id,
            workspace=fixture.workspace,
        )
        second = await attribution_service.attribute_verification_failure(
            task=fixture.task,
            task_attempt_id=fixture.worker_run.task_attempt_id,
            verification_run_id=run.verification_run_id,
            workspace=fixture.workspace,
        )
        assert first.attribution_id == second.attribution_id

        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            rows = await FailureAttributionRepository().list_for_task(
                uow.connection, fixture.task.task_id
            )
            await uow.commit()
        assert len(rows) == 1
    finally:
        if workspace is not None:
            await WorkspaceService(db_engine, root=root).cleanup(workspace=workspace)
        await db_engine.dispose()
