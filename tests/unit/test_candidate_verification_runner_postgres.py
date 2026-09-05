"""PostgreSQL proof for Blueprint §17.1 non-worker VerificationRun lineage.

This test is intentionally database-backed: it proves the widened generated
schema accepts a real FRONTEND_CANDIDATE run and persists ordinary Evidence
without manufacturing WorkerRun/TaskAttempt identities.
"""

from __future__ import annotations

from contextlib import suppress

import pytest

from engine.context.repo import repo_root
from engine.core.ids import uuid7
from engine.verification.checks import CheckSpec
from engine.verification.oracle import AcceptanceOracleService
from engine.verification.repository import VerificationRunRepository
from engine.verification.runner import VerificationRunnerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.worker_fixtures import build_worker_fixture


@pytest.mark.asyncio
async def test_frontend_candidate_revision_persists_real_verification_run(
    tmp_path,
) -> None:
    engine = new_engine()
    workspace = None
    try:
        fixture = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-FS69-CANDIDATE-VERIFY"
        )
        workspace = fixture.workspace
        check = CheckSpec(
            outcome_id=uuid7(),
            statement="candidate workspace can execute deterministic verification",
            kind="test",
            ref="frontend-candidate:smoke",
            command=["python3", "-c", "print('candidate-verification-ok')"],
        )
        oracle = await AcceptanceOracleService(engine).define(
            task=fixture.task,
            outcomes=[check],
        )
        candidate_id = uuid7()
        run = await VerificationRunnerService(
            engine, WorkspaceService(engine, root=repo_root())
        ).run_workspace_revision(
            task=fixture.task,
            workspace=workspace,
            oracle=oracle,
            subject_kind="FRONTEND_CANDIDATE",
            subject_id=candidate_id,
            revision_fingerprint="candidate-content-hash-v1",
            render_url_override=None,
            idempotency_key=f"candidate-verify:{candidate_id}:v1",
        )
        assert run.status == "PASSED"
        assert run.worker_run_id is None
        assert run.task_attempt_id is None
        assert run.subject_kind == "FRONTEND_CANDIDATE"
        assert run.subject_id == candidate_id
        assert run.evidence_refs

        # The repository reads the exact persisted shape back, rather than
        # this being only a Pydantic construction that SQL cannot store.
        from engine.truth.db import open_unit_of_work

        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            stored = await VerificationRunRepository().get_run(
                uow.connection, run.verification_run_id
            )
        assert stored is not None
        assert stored.subject_id == candidate_id
        assert stored.worker_run_id is None
    finally:
        if workspace is not None:
            with suppress(Exception):
                await WorkspaceService(engine, root=repo_root()).cleanup(
                    workspace=workspace
                )
        await engine.dispose()
