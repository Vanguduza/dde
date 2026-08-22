"""Chapter 6.4 Routing Simulation Model -- fixture generator (DDE-036).

Pure tests: every scenario class this module claims to support must
generate a real, deterministic adversarial fixture that genuinely drives
`engine.routing.rules.evaluate()` (never a fabricated/mocked routing
result) to the expected escalation, and must be byte-for-byte
reproducible from the same seed (Chapter 6.4: "simulation seeds ... are
persisted for reproducibility").
"""

from __future__ import annotations

from uuid import UUID

import pytest

from engine.core.errors import DdeError
from engine.routing.policy import HUMAN_DECISION_TASK
from engine.simulation.scenarios import (
    DEFERRED_SCENARIO_CLASSES,
    REAL_SCENARIO_CLASSES,
    SCENARIO_GENERATOR_INDEPENDENCE_VIOLATION,
    SCENARIO_HARD_GATE_APPROVAL_REQUIRED,
    SCENARIO_WORKER_OUTAGE,
    build_fixture,
    run_scenario,
)


def _ids() -> tuple[UUID, UUID]:
    from engine.core.ids import uuid7

    return uuid7(), uuid7()


@pytest.mark.parametrize(
    "scenario_class",
    [
        SCENARIO_WORKER_OUTAGE,
        SCENARIO_GENERATOR_INDEPENDENCE_VIOLATION,
        SCENARIO_HARD_GATE_APPROVAL_REQUIRED,
    ],
)
def test_real_scenario_escalates_to_human_decision(scenario_class: str) -> None:
    """Every real adversarial fixture genuinely eliminates every candidate
    through `engine.routing.rules.evaluate()`'s own gates -- never a
    fabricated result -- and lands on the real `HUMAN_DECISION_TASK`
    escalation."""
    tenant_id, project_id = _ids()
    result = run_scenario(
        scenario_class,
        seed="seed-1",
        tenant_id=tenant_id,
        project_id=project_id,
    )
    assert result.selected_profile_id == HUMAN_DECISION_TASK
    assert result.passed is True


def test_same_seed_produces_byte_identical_fixture() -> None:
    """Chapter 6.4: seeds are persisted for reproducibility -- the same
    seed must construct the exact same synthetic `Task` (same task_id),
    not merely an equivalent-looking one."""
    tenant_id, project_id = _ids()
    first = build_fixture(
        SCENARIO_WORKER_OUTAGE,
        seed="repro-seed",
        tenant_id=tenant_id,
        project_id=project_id,
    )
    second = build_fixture(
        SCENARIO_WORKER_OUTAGE,
        seed="repro-seed",
        tenant_id=tenant_id,
        project_id=project_id,
    )
    assert first.task.task_id == second.task.task_id
    assert first.task.model_dump() == second.task.model_dump()


def test_different_seed_produces_different_task_id() -> None:
    tenant_id, project_id = _ids()
    first = build_fixture(
        SCENARIO_WORKER_OUTAGE,
        seed="seed-a",
        tenant_id=tenant_id,
        project_id=project_id,
    )
    second = build_fixture(
        SCENARIO_WORKER_OUTAGE,
        seed="seed-b",
        tenant_id=tenant_id,
        project_id=project_id,
    )
    assert first.task.task_id != second.task.task_id


def test_unknown_scenario_class_is_refused() -> None:
    tenant_id, project_id = _ids()
    with pytest.raises(DdeError):
        build_fixture(
            "not_a_real_scenario",
            seed="seed-1",
            tenant_id=tenant_id,
            project_id=project_id,
        )


def test_deferred_scenario_classes_are_not_claimed_as_real() -> None:
    """Chapter 6.4 names capability gap / modality mismatch / budget
    exhaustion / environment incompatibility as example adversarial
    classes, but Stage 1's real, fixed worker-profile registry
    (`engine.routing.registry.PROFILES`) satisfies every workload class's
    own declared capability/environment requirement by construction, and
    gate 5 (capacity/budget) has no real signal at all yet -- so none of
    those four can be driven to a genuine elimination without fabricating
    a signal. This module must name that honestly, not silently claim
    support it cannot deliver."""
    assert set(REAL_SCENARIO_CLASSES).isdisjoint(DEFERRED_SCENARIO_CLASSES)
    for deferred in DEFERRED_SCENARIO_CLASSES:
        with pytest.raises(DdeError):
            build_fixture(
                deferred, seed="seed-1", tenant_id=UUID(int=0), project_id=UUID(int=0)
            )
