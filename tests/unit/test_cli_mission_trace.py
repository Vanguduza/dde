"""Unit tests for `interfaces.cli.mission_trace`'s pure logic (Chapter 19.1
unit test type). Real production code always writes `Evidence.
independence_flags["independent"] = True` (`engine.verification.runner`
never dispatches to a worker profile at all), so an end-to-end fixture alone
would never exercise the "independence check actually rejects a bad row"
branch. These tests hand-build a `MissionTrace` to prove
`independence_proofs()` is a real, re-derived check -- not a pass-through of
a stored flag -- and that the renderer/exit-code logic behaves for both a
complete and an incomplete trace, without touching a database.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from engine.contracts.evidence import Evidence
from engine.contracts.mission import Mission
from engine.contracts.task import Task
from engine.contracts.task_graph import TaskGraph
from engine.contracts.verification_run import VerificationRun
from engine.contracts.worker_run import WorkerRun
from engine.core.errors import DdeError
from interfaces.cli.mission_trace import (
    EXIT_INCOMPLETE,
    EXIT_OK,
    MISSION_TRACE_INCOMPLETE,
    IndependenceProof,
    MissionTrace,
    TaskTrace,
    VerificationRunTrace,
    WorkerRunTrace,
    independence_proofs,
    render_mission_trace,
    require_complete_trace,
    trace_exit_code,
)

NOW = datetime.now(UTC)


def _mission() -> Mission:
    return Mission(
        mission_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        slug="mission-trace-unit",
        title="Unit test mission",
        intent="Exercise the trace renderer",
        success_definition="dde mission trace proves independence",
        scope=["engine"],
        requirement_refs=[],
        status="ACTIVE",
        autonomy_ceiling=2,
        lock_version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _task(mission: Mission, graph_id: UUID) -> Task:
    return Task(
        task_id=uuid4(),
        tenant_id=mission.tenant_id,
        project_id=mission.project_id,
        mission_id=mission.mission_id,
        graph_id=graph_id,
        title="Unit test task",
        intent="Exercise the trace renderer",
        task_class="verification",
        requirement_refs=[],
        feature_refs=[],
        success_criteria=["Behaviour is verified"],
        expected_write_scope=["engine"],
        expected_read_scope=["engine"],
        blast_radius="local",
        risk_class="low",
        estimated_effort="xs",
        autonomy_ceiling=2,
        requires_approval=False,
        status="COMPLETED",
        lock_version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _task_graph(mission: Mission, graph_id: UUID) -> TaskGraph:
    return TaskGraph(
        graph_id=graph_id,
        tenant_id=mission.tenant_id,
        project_id=mission.project_id,
        mission_id=mission.mission_id,
        version=1,
        status="APPROVED",
        planning_mode="template",
        planner_policy_version="planner-v1",
        rationale="unit test fixture",
        open_questions=[],
        graph_hash="c" * 64,
        created_by_principal=uuid4(),
        lock_version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _worker_run(mission: Mission) -> WorkerRun:
    return WorkerRun(
        run_id=uuid4(),
        tenant_id=mission.tenant_id,
        project_id=mission.project_id,
        mission_id=mission.mission_id,
        task_attempt_id=uuid4(),
        sequence=1,
        execution_plan_id=uuid4(),
        worker_id="worker-1",
        worker_profile_id="profile.deterministic_runner",
        environment_id=uuid4(),
        workspace_id=uuid4(),
        context_package_id=uuid4(),
        policy_version="worker-manager-v1",
        lease_set_hash="deadbeef",
        status="COMPLETED",
        created_at=NOW,
        updated_at=NOW,
    )


def _verification_run(
    mission: Mission, task: Task, worker_run: WorkerRun
) -> VerificationRun:
    return VerificationRun(
        verification_run_id=uuid4(),
        tenant_id=mission.tenant_id,
        project_id=mission.project_id,
        mission_id=mission.mission_id,
        task_id=task.task_id,
        task_attempt_id=worker_run.task_attempt_id,
        worker_run_id=worker_run.run_id,
        workspace_id=worker_run.workspace_id,
        oracle_id=uuid4(),
        sequence=1,
        status="PASSED",
        confidence=1.0,
        check_results=[],
        outcome_results=[],
        negative_case_results=[],
        evidence_refs=[],
        started_at=NOW,
        ended_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


def _evidence(
    mission: Mission,
    task: Task,
    verification_run: VerificationRun,
    *,
    generator_worker_profile_id: str,
    verifier: str,
    independent: bool,
) -> Evidence:
    return Evidence(
        evidence_id=uuid4(),
        tenant_id=mission.tenant_id,
        project_id=mission.project_id,
        mission_id=mission.mission_id,
        task_id=task.task_id,
        verification_run_id=verification_run.verification_run_id,
        integrated_revision="deadbeef",
        evidence_type="test",
        artifact_refs=[],
        content_hash="a" * 64,
        signature="b" * 64,
        produced_by="capability:engine.verification.runner",
        independence_flags={
            "generator_worker_profile_id": generator_worker_profile_id,
            "verifier": verifier,
            "independent": independent,
        },
        recorded_at=NOW,
        status="RECORDED",
        created_at=NOW,
        updated_at=NOW,
    )


def _build_trace(
    *, generator_worker_profile_id: str, verifier: str, independent: bool
) -> tuple[MissionTrace, list[IndependenceProof]]:
    mission = _mission()
    graph_id = uuid4()
    task = _task(mission, graph_id)
    worker_run = _worker_run(mission)
    verification_run = _verification_run(mission, task, worker_run)
    evidence = _evidence(
        mission,
        task,
        verification_run,
        generator_worker_profile_id=generator_worker_profile_id,
        verifier=verifier,
        independent=independent,
    )
    trace = MissionTrace(
        mission=mission,
        tasks=[
            TaskTrace(
                task=task,
                task_graph=_task_graph(mission, graph_id),
                context_packages=[],
                route_decisions=[],
                execution_plans=[],
                worker_runs=[
                    WorkerRunTrace(
                        run=worker_run,
                        workspace=None,
                        verification_runs=[
                            VerificationRunTrace(
                                run=verification_run, evidence=[evidence]
                            )
                        ],
                    )
                ],
                integration_proposals=[],
            )
        ],
    )
    proofs = independence_proofs(trace)
    return trace, proofs


def test_independence_proof_holds_when_generator_and_verifier_genuinely_differ() -> (
    None
):
    trace, proofs = _build_trace(
        generator_worker_profile_id="profile.deterministic_runner",
        verifier="engine.verification.runner",
        independent=True,
    )
    assert len(proofs) == 1
    assert proofs[0].independent is True
    assert trace_exit_code(trace, proofs) == EXIT_OK
    require_complete_trace(trace, proofs)  # must not raise

    output = render_mission_trace(trace, proofs)
    assert "INDEPENDENT" in output
    assert "Chapter 1 acceptance sentence: PROVEN" in output
    assert proofs[0].content_hash in output
    assert proofs[0].generator_worker_profile_id in output


def test_independence_proof_rejects_a_verifier_that_is_actually_the_generator() -> None:
    """A real check, not a rubber stamp: even a stale `independent: True`
    flag is not enough if the claimed generator and verifier identities are
    actually the same worker profile."""
    trace, proofs = _build_trace(
        generator_worker_profile_id="profile.deterministic_runner",
        verifier="profile.deterministic_runner",
        independent=True,
    )
    assert len(proofs) == 1
    assert proofs[0].independent is False
    assert trace_exit_code(trace, proofs) == EXIT_INCOMPLETE

    output = render_mission_trace(trace, proofs)
    assert "NOT PROVEN INDEPENDENT" in output
    assert "Chapter 1 acceptance sentence: NOT YET PROVEN" in output
    with pytest.raises(DdeError) as excinfo:
        require_complete_trace(trace, proofs)
    assert excinfo.value.error_code == MISSION_TRACE_INCOMPLETE


def test_independence_proof_rejects_a_falsely_stored_independent_flag() -> None:
    """Even if `independent` were stored `True` while `verifier` were empty
    (never happens in real `engine.verification.runner` output, but a real
    check must not trust the boolean alone), the proof must be `False`."""
    trace, proofs = _build_trace(
        generator_worker_profile_id="profile.deterministic_runner",
        verifier="",
        independent=True,
    )
    assert proofs[0].independent is False


def test_require_complete_trace_raises_on_a_mission_with_no_tasks() -> None:
    mission = _mission()
    empty_trace = MissionTrace(mission=mission, tasks=[])
    assert trace_exit_code(empty_trace, []) == EXIT_INCOMPLETE
    with pytest.raises(DdeError) as excinfo:
        require_complete_trace(empty_trace, [])
    assert excinfo.value.error_code == MISSION_TRACE_INCOMPLETE
