"""DDE-069 M7 — the write path and promotion gate against real PostgreSQL.

Proves the persisted half of the guarantees the pure tests establish: a
refusal is recorded rather than swallowed, an applied mutation actually
moves the graph and the candidate, an undo compensates without rewriting
history, and promotion refuses with every blocking reason rather than the
first one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from engine.contracts.verification_run import CheckResult, VerificationRun
from engine.core.errors import DdeError
from engine.studio.candidates.lifecycle import CandidateState
from engine.studio.candidates.promotion import PromotionService
from engine.studio.candidates.service import CandidateService
from engine.studio.locks.service import LockService
from engine.studio.mutations.executor import MutationExecutor
from engine.studio.mutations.planner import MutationRequest
from engine.studio.mutations.projection import change_count
from engine.studio.pxg.service import NodeInput, PxgService
from tests.support.db import new_engine, seed_tenant


async def _project(engine):
    fixture = await seed_tenant(engine)
    scope = {"tenant_id": fixture.tenant_id, "project_id": fixture.project_id}
    await PxgService(engine).apply(
        **scope,
        nodes=[
            NodeInput(pxg_key="screens/checkout", node_kind="screen", title="Checkout"),
            NodeInput(
                pxg_key="screens/checkout#hero",
                node_kind="region",
                title="Hero",
                parent_key="screens/checkout",
                attributes={"spacing": "space2"},
            ),
        ],
    )
    return fixture, scope


def _run(**kinds: str) -> VerificationRun:
    now = datetime.now(UTC)
    return VerificationRun(
        verification_run_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        mission_id=uuid4(),
        task_id=uuid4(),
        task_attempt_id=uuid4(),
        worker_run_id=uuid4(),
        workspace_id=uuid4(),
        oracle_id=uuid4(),
        sequence=1,
        status="PASSED",
        confidence=1.0,
        check_results=[
            CheckResult(
                check_ref=f"screens/checkout:{kind}",
                kind=kind,
                command=[],
                exit_code=0 if status == "PASSED" else 1,
                stdout="",
                stderr="",
                duration_ms=1,
                timed_out=False,
                status=status,
            )
            for kind, status in kinds.items()
        ],
        outcome_results=[],
        negative_case_results=[],
        evidence_refs=[],
        started_at=now,
        created_at=now,
        updated_at=now,
    )


async def _ready_candidate(engine, scope):
    candidates = CandidateService(engine)
    candidate = await candidates.create(
        **scope,
        title="Direction A",
        origin="DIRECT_EDIT",
        scope_keys=["screens/checkout"],
    )
    for target in (
        CandidateState.GENERATING,
        CandidateState.GENERATED,
        CandidateState.MATERIALIZING,
        CandidateState.RENDERING,
        CandidateState.READY,
    ):
        await candidates.transition(
            **scope, candidate_id=candidate.candidate_id, target=target
        )
    return candidate


@pytest.mark.asyncio
async def test_editing_a_candidate_never_touches_the_accepted_graph() -> None:
    """The isolation guarantee, stated as a test.

    A candidate's edit must be visible in *its* graph and invisible in the
    accepted one. The executor writes no accepted nodes at all, so this
    protection is structural rather than a rule someone has to remember.
    """
    engine = new_engine()
    try:
        _, scope = await _project(engine)
        candidate = await _ready_candidate(engine, scope)
        executor = MutationExecutor(engine)

        outcome = await executor.apply(
            **scope,
            candidate_id=candidate.candidate_id,
            requests=[
                MutationRequest(
                    operation="SET_PROPERTY",
                    target_key="screens/checkout#hero",
                    origin="INSPECTOR",
                    payload={"property": "spacing", "value": "space6"},
                )
            ],
        )
        assert outcome.fully_applied
        assert outcome.candidate_state is CandidateState.DIRTY

        accepted = await PxgService(engine).load(**scope)
        hero = accepted.node_by_key("screens/checkout#hero")
        assert hero is not None
        assert hero.attributes["spacing"] == "space2", (
            "accepted state must be untouched by candidate editing"
        )
        assert accepted.revision == 1, "the accepted revision did not move"

        effective = await executor.candidate_graph(
            **scope, candidate_id=candidate.candidate_id
        )
        hero = effective.node_by_key("screens/checkout#hero")
        assert hero is not None
        assert hero.attributes["spacing"] == "space6", "the candidate sees its own edit"

        history = await executor.history(**scope, candidate_id=candidate.candidate_id)
        assert [item.status for item in history] == ["APPLIED"]
        assert history[0].sequence == 1
        assert history[0].inverse["value"] == "space2"
        assert change_count(history) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_promotion_is_the_only_writer_of_accepted_nodes() -> None:
    engine = new_engine()
    try:
        _, scope = await _project(engine)
        candidate = await _ready_candidate(engine, scope)
        candidates = CandidateService(engine)
        executor = MutationExecutor(engine)

        await executor.apply(
            **scope,
            candidate_id=candidate.candidate_id,
            requests=[
                MutationRequest(
                    operation="SET_PROPERTY",
                    target_key="screens/checkout#hero",
                    origin="INSPECTOR",
                    payload={"property": "spacing", "value": "space6"},
                ),
                MutationRequest(
                    operation="ADD",
                    target_key="screens/checkout#promo",
                    origin="CHAT",
                    payload={"node_kind": "component", "title": "Promo"},
                ),
            ],
        )
        assert (await PxgService(engine).load(**scope)).revision == 1

        for target in (
            CandidateState.VERIFYING,
            CandidateState.VERIFIED,
            CandidateState.PROMOTABLE,
        ):
            await candidates.transition(
                **scope, candidate_id=candidate.candidate_id, target=target
            )
        await PromotionService(engine).promote(
            **scope,
            candidate_id=candidate.candidate_id,
            verification_runs=(_run(silhouette="PASSED", visual_critique="PASSED"),),
        )

        accepted = await PxgService(engine).load(**scope)
        assert accepted.revision == 2, "one merge is one revision"
        hero = accepted.node_by_key("screens/checkout#hero")
        assert hero is not None and hero.attributes["spacing"] == "space6"
        promo = accepted.node_by_key("screens/checkout#promo")
        assert promo is not None and promo.title == "Promo"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_a_refusal_is_recorded_rather_than_swallowed() -> None:
    """ "The studio silently did nothing" must never be the outcome."""
    engine = new_engine()
    try:
        _, scope = await _project(engine)
        candidate = await _ready_candidate(engine, scope)
        await LockService(engine).create(
            **scope,
            lock_kind="STYLE",
            scope_key="screens/checkout",
            reason="brand review in progress",
            created_by=uuid4(),
        )
        executor = MutationExecutor(engine)

        outcome = await executor.apply(
            **scope,
            candidate_id=candidate.candidate_id,
            requests=[
                MutationRequest(
                    operation="SET_PROPERTY",
                    target_key="screens/checkout#hero",
                    origin="CHAT",
                    payload={"property": "spacing", "value": "space6"},
                )
            ],
        )
        assert outcome.applied == ()
        assert len(outcome.refused) == 1
        refusal = outcome.refused[0]
        assert refusal.status == "REFUSED"
        assert refusal.refusal_code == "LOCK_DENIED"
        assert "brand review in progress" in (refusal.refusal_detail or "")

        # Neither the accepted graph nor the candidate's own view moved.
        graph = await executor.candidate_graph(
            **scope, candidate_id=candidate.candidate_id
        )
        hero = graph.node_by_key("screens/checkout#hero")
        assert hero is not None and hero.attributes["spacing"] == "space2"

        # And the refusal is durable, so the UI can explain it later.
        history = await executor.history(**scope, candidate_id=candidate.candidate_id)
        assert [item.status for item in history] == ["REFUSED"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_undo_compensates_without_rewriting_history() -> None:
    engine = new_engine()
    try:
        _, scope = await _project(engine)
        candidate = await _ready_candidate(engine, scope)
        executor = MutationExecutor(engine)

        applied = await executor.apply(
            **scope,
            candidate_id=candidate.candidate_id,
            requests=[
                MutationRequest(
                    operation="SET_PROPERTY",
                    target_key="screens/checkout#hero",
                    origin="INSPECTOR",
                    payload={"property": "spacing", "value": "space6"},
                )
            ],
        )
        original = applied.applied[0]

        await executor.revert(
            **scope,
            candidate_id=candidate.candidate_id,
            mutation_id=original.mutation_id,
        )

        graph = await executor.candidate_graph(
            **scope, candidate_id=candidate.candidate_id
        )
        hero = graph.node_by_key("screens/checkout#hero")
        assert hero is not None
        assert hero.attributes["spacing"] == "space2", "value restored"

        history = await executor.history(**scope, candidate_id=candidate.candidate_id)
        assert [item.status for item in history] == ["REVERTED", "APPLIED"]
        assert history[0].mutation_id == original.mutation_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_promotion_reports_every_blocker_not_just_the_first() -> None:
    engine = new_engine()
    try:
        _, scope = await _project(engine)
        candidate = await _ready_candidate(engine, scope)
        gate = PromotionService(engine)

        decision = await gate.evaluate(**scope, candidate_id=candidate.candidate_id)
        assert decision.allowed is False
        blockers = {item.name for item in decision.blockers}
        # READY, no mutations, no verification: three separate problems,
        # all reported together.
        assert blockers == {"state", "mutations", "visual_verification"}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_promotion_refuses_without_visual_evidence_and_accepts_with_it() -> None:
    engine = new_engine()
    try:
        _, scope = await _project(engine)
        candidate = await _ready_candidate(engine, scope)
        candidates = CandidateService(engine)
        executor = MutationExecutor(engine)
        gate = PromotionService(engine)

        await executor.apply(
            **scope,
            candidate_id=candidate.candidate_id,
            requests=[
                MutationRequest(
                    operation="SET_PROPERTY",
                    target_key="screens/checkout#hero",
                    origin="INSPECTOR",
                    payload={"property": "spacing", "value": "space6"},
                )
            ],
        )
        for target in (
            CandidateState.VERIFYING,
            CandidateState.VERIFIED,
            CandidateState.PROMOTABLE,
        ):
            await candidates.transition(
                **scope, candidate_id=candidate.candidate_id, target=target
            )

        # No evidence at all.
        with pytest.raises(DdeError) as excinfo:
            await gate.promote(**scope, candidate_id=candidate.candidate_id)
        assert excinfo.value.error_code == "POLICY_DENIED"
        assert any(
            item["gate"] == "visual_verification"
            for item in excinfo.value.details["blockers"]
        )

        # Half the required kinds ran.
        decision = await gate.evaluate(
            **scope,
            candidate_id=candidate.candidate_id,
            verification_runs=(_run(silhouette="PASSED"),),
        )
        visual = next(
            item for item in decision.gates if item.name == "visual_verification"
        )
        assert visual.passed is False
        assert "visual_critique" in visual.detail

        # A required check errored -- unavailable is not approval.
        decision = await gate.evaluate(
            **scope,
            candidate_id=candidate.candidate_id,
            verification_runs=(_run(silhouette="PASSED", visual_critique="ERRORED"),),
        )
        visual = next(
            item for item in decision.gates if item.name == "visual_verification"
        )
        assert visual.passed is False
        assert "ERRORED" in visual.detail

        # A required check failed.
        decision = await gate.evaluate(
            **scope,
            candidate_id=candidate.candidate_id,
            verification_runs=(_run(silhouette="PASSED", visual_critique="FAILED"),),
        )
        assert decision.allowed is False

        # Everything passed.
        promoted = await gate.promote(
            **scope,
            candidate_id=candidate.candidate_id,
            verification_runs=(_run(silhouette="PASSED", visual_critique="PASSED"),),
        )
        assert promoted.state == CandidateState.PROMOTED.value
        assert promoted.promoted_at is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_a_stale_candidate_cannot_promote() -> None:
    """The accepted base moved; the candidate describes a project that no
    longer exists."""
    engine = new_engine()
    try:
        _, scope = await _project(engine)
        candidate = await _ready_candidate(engine, scope)
        candidates = CandidateService(engine)
        executor = MutationExecutor(engine)

        await executor.apply(
            **scope,
            candidate_id=candidate.candidate_id,
            requests=[
                MutationRequest(
                    operation="SET_PROPERTY",
                    target_key="screens/checkout#hero",
                    origin="INSPECTOR",
                    payload={"property": "spacing", "value": "space6"},
                )
            ],
        )
        for target in (
            CandidateState.VERIFYING,
            CandidateState.VERIFIED,
            CandidateState.PROMOTABLE,
        ):
            await candidates.transition(
                **scope, candidate_id=candidate.candidate_id, target=target
            )

        # Someone else advances the accepted graph.
        await PxgService(engine).apply(
            **scope,
            nodes=[
                NodeInput(
                    pxg_key="screens/settings", node_kind="screen", title="Settings"
                )
            ],
        )

        decision = await PromotionService(engine).evaluate(
            **scope,
            candidate_id=candidate.candidate_id,
            verification_runs=(_run(silhouette="PASSED", visual_critique="PASSED"),),
        )
        assert decision.allowed is False
        staleness = next(item for item in decision.gates if item.name == "staleness")
        assert staleness.passed is False
        assert "Rebase" in staleness.detail
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_a_lock_created_after_the_candidate_blocks_promotion() -> None:
    """Otherwise locking a region would not stop work already in flight
    from landing on it -- the case locks exist for."""
    engine = new_engine()
    try:
        _, scope = await _project(engine)
        candidate = await _ready_candidate(engine, scope)
        candidates = CandidateService(engine)
        executor = MutationExecutor(engine)

        await executor.apply(
            **scope,
            candidate_id=candidate.candidate_id,
            requests=[
                MutationRequest(
                    operation="SET_PROPERTY",
                    target_key="screens/checkout#hero",
                    origin="INSPECTOR",
                    payload={"property": "spacing", "value": "space6"},
                )
            ],
        )
        for target in (
            CandidateState.VERIFYING,
            CandidateState.VERIFIED,
            CandidateState.PROMOTABLE,
        ):
            await candidates.transition(
                **scope, candidate_id=candidate.candidate_id, target=target
            )

        await LockService(engine).create(
            **scope,
            lock_kind="SCREEN",
            scope_key="screens/checkout",
            reason="frozen for release",
            created_by=uuid4(),
        )
        decision = await PromotionService(engine).evaluate(
            **scope,
            candidate_id=candidate.candidate_id,
            verification_runs=(_run(silhouette="PASSED", visual_critique="PASSED"),),
        )
        assert decision.allowed is False
        assert any(item.name == "locks" for item in decision.blockers)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_candidate_state_transitions_are_governed_in_the_database() -> None:
    engine = new_engine()
    try:
        _, scope = await _project(engine)
        candidates = CandidateService(engine)
        candidate = await candidates.create(
            **scope,
            title="Direction B",
            origin="DESIGN_ARTIFACT",
            scope_keys=["screens/checkout"],
        )
        assert candidate.state == CandidateState.REQUESTED.value
        assert candidate.base_pxg_revision == 1

        with pytest.raises(DdeError) as excinfo:
            await candidates.transition(
                **scope,
                candidate_id=candidate.candidate_id,
                target=CandidateState.PROMOTED,
            )
        assert excinfo.value.error_code == "POLICY_DENIED"

        view = await candidates.view(**scope, candidate_id=candidate.candidate_id)
        assert view.stale is False
        assert view.state is CandidateState.REQUESTED
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_an_unscoped_candidate_is_refused() -> None:
    engine = new_engine()
    try:
        _, scope = await _project(engine)
        with pytest.raises(DdeError) as excinfo:
            await CandidateService(engine).create(
                **scope, title="x", origin="DIRECT_EDIT", scope_keys=[]
            )
        assert excinfo.value.error_code == "VALIDATION_FAILED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_a_lock_without_a_reason_is_refused() -> None:
    engine = new_engine()
    try:
        _, scope = await _project(engine)
        with pytest.raises(DdeError) as excinfo:
            await LockService(engine).create(
                **scope,
                lock_kind="STYLE",
                scope_key="screens/checkout",
                reason="   ",
                created_by=uuid4(),
            )
        assert excinfo.value.error_code == "VALIDATION_FAILED"
    finally:
        await engine.dispose()
