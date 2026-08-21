"""Chapter 5.13 eval corpus lifecycle (`engine.context.eval_corpus`),
tested against a real PostgreSQL schema and a real `MERGED`
`IntegrationProposal` produced through `tests.support.mission_trace_fixtures`
-- exactly the "real completed mission" Chapter 5.13 requires, not a
hand-inserted row.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.context.eval_corpus import EvalCorpusService
from engine.integration.repository import IntegrationProposalRepository
from engine.truth.db import open_unit_of_work
from tests.support.db import new_engine
from tests.support.mission_trace_fixtures import build_traceable_mission


@pytest.mark.asyncio
async def test_build_case_from_integration_derives_required_refs_mechanically(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    try:
        trace = await build_traceable_mission(
            engine, tmp_path, mission_slug="MISSION-EVAL-BUILD"
        )
        assert trace.proposal.status == "MERGED"
        service = EvalCorpusService(engine)

        case = await service.build_case_from_integration(
            tenant_id=trace.tenant.tenant_id,
            project_id=trace.tenant.project_id,
            source_proposal_id=trace.proposal.proposal_id,
            source_mission_id=trace.mission_id,
            source_task_id=trace.advanced.task.task_id,
            task_class=trace.advanced.task.task_class,
            task_requirement_refs=trace.advanced.task.requirement_refs,
        )

        assert case.status == "draft"
        assert case.frozen_version is None
        # Mechanically derived (Chapter 5.13 point 2): every changed path
        # from the accepted diff, plus the task's requirement refs -- never
        # guessed ahead of time.
        for path in trace.proposal.changed_paths:
            assert path in case.required_refs
        for ref in trace.advanced.task.requirement_refs:
            assert ref in case.required_refs
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_build_case_from_integration_rejects_non_merged_proposal(
    tmp_path: Path,
) -> None:
    """Chapter 5.13 point 1: a case must come from a real, accepted diff --
    a proposal still in flight (not yet MERGED) must be refused."""
    engine = new_engine()
    try:
        trace = await build_traceable_mission(
            engine, tmp_path, mission_slug="MISSION-EVAL-REJECT"
        )
        async with open_unit_of_work(
            engine,
            tenant_id=trace.tenant.tenant_id,
            project_id=trace.tenant.project_id,
        ) as uow:
            await IntegrationProposalRepository().update_proposal(
                uow.connection,
                trace.proposal.proposal_id,
                fields={"status": "QUEUED"},
            )
            await uow.commit()
        service = EvalCorpusService(engine)

        with pytest.raises(ValueError, match="MERGED"):
            await service.build_case_from_integration(
                tenant_id=trace.tenant.tenant_id,
                project_id=trace.tenant.project_id,
                source_proposal_id=trace.proposal.proposal_id,
                source_mission_id=trace.mission_id,
                source_task_id=trace.advanced.task.task_id,
                task_class=trace.advanced.task.task_class,
                task_requirement_refs=trace.advanced.task.requirement_refs,
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_freeze_case_requires_draft_and_list_excludes_unfrozen(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    try:
        trace = await build_traceable_mission(
            engine, tmp_path, mission_slug="MISSION-EVAL-FREEZE"
        )
        service = EvalCorpusService(engine)
        case = await service.build_case_from_integration(
            tenant_id=trace.tenant.tenant_id,
            project_id=trace.tenant.project_id,
            source_proposal_id=trace.proposal.proposal_id,
            source_mission_id=trace.mission_id,
            source_task_id=trace.advanced.task.task_id,
            task_class=trace.advanced.task.task_class,
            task_requirement_refs=trace.advanced.task.requirement_refs,
        )

        before_freeze = await service.list_active_corpus(
            tenant_id=trace.tenant.tenant_id, project_id=trace.tenant.project_id
        )
        assert before_freeze == []  # a draft case is not yet part of the corpus

        frozen = await service.freeze_case(
            tenant_id=trace.tenant.tenant_id,
            project_id=trace.tenant.project_id,
            eval_case_id=case.eval_case_id,
        )
        assert frozen.status == "frozen"
        assert frozen.frozen_version == 1

        after_freeze = await service.list_active_corpus(
            tenant_id=trace.tenant.tenant_id, project_id=trace.tenant.project_id
        )
        assert [item.eval_case_id for item in after_freeze] == [case.eval_case_id]

        with pytest.raises(ValueError, match="not draft"):
            await service.freeze_case(
                tenant_id=trace.tenant.tenant_id,
                project_id=trace.tenant.project_id,
                eval_case_id=case.eval_case_id,
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_retire_case_is_terminal_and_never_deletes(tmp_path: Path) -> None:
    engine = new_engine()
    try:
        trace = await build_traceable_mission(
            engine, tmp_path, mission_slug="MISSION-EVAL-RETIRE"
        )
        service = EvalCorpusService(engine)
        case = await service.build_case_from_integration(
            tenant_id=trace.tenant.tenant_id,
            project_id=trace.tenant.project_id,
            source_proposal_id=trace.proposal.proposal_id,
            source_mission_id=trace.mission_id,
            source_task_id=trace.advanced.task.task_id,
            task_class=trace.advanced.task.task_class,
            task_requirement_refs=trace.advanced.task.requirement_refs,
        )
        await service.freeze_case(
            tenant_id=trace.tenant.tenant_id,
            project_id=trace.tenant.project_id,
            eval_case_id=case.eval_case_id,
        )

        with pytest.raises(ValueError, match="non-empty reason"):
            await service.retire_case(
                tenant_id=trace.tenant.tenant_id,
                project_id=trace.tenant.project_id,
                eval_case_id=case.eval_case_id,
                reason="   ",
            )

        retired = await service.retire_case(
            tenant_id=trace.tenant.tenant_id,
            project_id=trace.tenant.project_id,
            eval_case_id=case.eval_case_id,
            reason="superseded by a fresher case for the same task class",
        )
        assert retired.status == "retired"
        assert retired.retired_reason is not None

        corpus = await service.list_active_corpus(
            tenant_id=trace.tenant.tenant_id, project_id=trace.tenant.project_id
        )
        assert corpus == []  # retired, never part of the active corpus again

        async with open_unit_of_work(
            engine,
            tenant_id=trace.tenant.tenant_id,
            project_id=trace.tenant.project_id,
        ) as uow:
            all_cases = await service._repository.list_for_project(  # noqa: SLF001
                uow.connection, trace.tenant.tenant_id, trace.tenant.project_id
            )
            await uow.commit()
        assert any(item.eval_case_id == case.eval_case_id for item in all_cases)
    finally:
        await engine.dispose()
