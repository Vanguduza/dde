"""Recovery-boundary contract test (comparable-systems adoption #9, second
half): after a checkpoint replay boundary, a forced `ContextPackage`
rebuild over changed inputs must yield a *fresh* content hash -- never a
stale carry-over of the pre-replay package's `assembly_hash`.

Exercises the real production writers (`ContextService.compile()` and the
Chapter 12.1 `CheckpointService.record()` + `is_valid`) against real
PostgreSQL. The checkpoint hangs off a real
`build_verification_fixture` chain -- a real COMPLETED `WorkerRun` with
its real `TaskAttempt`, `ExecutionPlan` and `ContextPackage` -- so every
`checkpoints` foreign key resolves exactly as the production call sites
(`WorkerManagerService`, `VerificationRunnerService`) record them. The
"replay" here is the durable continuation contract a recovering session
reads, exactly as Chapter 12.5's planner does.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.context.model import ContextBudgetExceeded
from engine.context.repo import repo_root
from engine.context.repository import ContextRepository
from engine.context.service import ContextService
from engine.recovery.checkpoint_service import CheckpointService
from engine.truth.db import open_unit_of_work
from engine.workers.repository import WorkerEventRepository
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.verification_fixtures import build_verification_fixture


@pytest.mark.asyncio
async def test_context_package_rebuild_after_checkpoint_replay_is_fresh(
    tmp_path: Path,
) -> None:
    """Pre-replay compile -> durable checkpoint -> "replay": the recovered
    session finds an input file changed and recompiles. The rebuilt
    package must carry a different `assembly_hash` (fresh content hash)
    and a new version -- and the pre-replay checkpoint must still validate
    against its own recorded context identity, proving staleness was
    detected rather than papered over."""
    root = repo_root()
    engine = new_engine()
    workspace = None
    try:
        fixture = await build_verification_fixture(
            engine, tmp_path, mission_slug="MISSION-CTX-REPLAY-BOUNDARY"
        )
        workspace = fixture.workspace
        # The fixture provisioned its synthetic corpus (and compiled the
        # plan's ContextPackage against it) at tmp_path -- the same
        # controlled tree this test mutates across the replay boundary.
        service = ContextService(engine, root=tmp_path)

        pre_replay = await service.compile(task=fixture.task)
        assert not isinstance(pre_replay, ContextBudgetExceeded)
        # Recompiling identical inputs yields the identical assembly hash
        # (the fixture's own compile is the first version of this task).
        assert pre_replay.assembly_hash == fixture.context_package.assembly_hash

        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            worker_events = await WorkerEventRepository().list_for_run(
                uow.connection, fixture.worker_run.run_id
            )
            await uow.commit()
        sequence = worker_events[-1].sequence if worker_events else 0

        checkpoints = CheckpointService(engine)
        checkpoint = await checkpoints.record(
            run=fixture.worker_run,
            task_id=fixture.task.task_id,
            workspace_revision=fixture.workspace.current_revision
            or fixture.workspace.base_revision
            or "",
            event_sequence=sequence,
            completed_work=["compile-context"],
            verified_work=[],
            pending_work=["rebuild-context-after-replay"],
            known_failures=[],
            next_action="rebuild context package",
            do_not_repeat=[],
            artifact_refs=[],
            lease_refs=[],
            idempotency_key="ctx-replay-boundary-checkpoint-1",
        )
        assert checkpoints.is_valid(checkpoint)
        assert checkpoint.context_package_id == fixture.worker_run.context_package_id

        # The recovery boundary: the corpus changed while the mission was
        # down. A fresh compile must observe it.
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text(
            agents_md.read_text(encoding="utf-8") + "\n\n## Post-replay amendment\n\n"
            "A session recovering across a replay boundary must recompile "
            "the context package before reusing it.\n",
            encoding="utf-8",
        )

        post_replay = await service.compile(task=fixture.task)
        assert not isinstance(post_replay, ContextBudgetExceeded)

        assert post_replay.assembly_hash != pre_replay.assembly_hash
        assert post_replay.version == pre_replay.version + 1
        assert post_replay.package_id != pre_replay.package_id

        # The checkpoint still binds to the *pre-replay* context identity:
        # replay validation is against what was true when it was written.
        assert checkpoint.context_package_id == fixture.worker_run.context_package_id
        assert checkpoints.is_valid(checkpoint)

        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            versions = await ContextRepository().list_versions_for_task(
                uow.connection, fixture.task.task_id
            )
            await uow.commit()
        assert versions[-1].package_id == post_replay.package_id
        assert [item.assembly_hash for item in versions][-2:] == [
            pre_replay.assembly_hash,
            post_replay.assembly_hash,
        ]
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=root).cleanup(workspace=workspace)
        await engine.dispose()
