"""Chapter 12.3 recovery matrix (pure policy, no I/O)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from engine.core.errors import DdeError
from engine.recovery.matrix import (
    MERGE_CONFLICT_REPLAN_AFTER,
    WORKER_FAILURE_REROUTE_AFTER,
    attempt_survives_run_failure,
    classify_dispositions,
    decide,
)


def test_authorization_never_allows_a_new_worker_run() -> None:
    decision = decide("AUTHORIZATION_FAILURE", occurrence_count=1)
    assert decision.allow_new_worker_run is False
    assert decision.requires_human is True
    assert decision.action == "request_approval"


def test_worker_failure_reroutes_when_repeated() -> None:
    first = decide("WORKER_COMMAND_FAILED", occurrence_count=1)
    assert first.failure_class == "WORKER_FAILURE"
    assert first.allow_new_worker_run is True
    repeated = decide("WORKER_FAILURE", occurrence_count=WORKER_FAILURE_REROUTE_AFTER)
    assert repeated.allow_new_worker_run is False
    assert repeated.action == "reroute"


def test_side_effect_unknown_blocks_until_reconciled() -> None:
    blocked = decide("SIDE_EFFECT_UNKNOWN", occurrence_count=1, unreconciled=True)
    assert blocked.allow_new_worker_run is False
    assert blocked.error_code == "EFFECT_UNKNOWN"
    clear = decide("SIDE_EFFECT_UNKNOWN", occurrence_count=1, unreconciled=False)
    assert clear.allow_new_worker_run is True


def test_merge_conflict_replans_after_more_than_two() -> None:
    repair = decide("MERGE_CONFLICT", occurrence_count=2)
    assert repair.action == "repair"
    assert repair.requires_replan is False
    escalated = decide("MERGE_CONFLICT", occurrence_count=MERGE_CONFLICT_REPLAN_AFTER)
    assert escalated.requires_replan is True


def test_environment_failure_refuses_a_retry_on_the_same_environment() -> None:
    decision = decide("ENVIRONMENT_FAILURE", occurrence_count=1)
    assert decision.allow_new_worker_run is False
    assert decision.action == "replace_environment"
    assert attempt_survives_run_failure(
        "ENVIRONMENT_FAILURE", worker_failure_occurrence_count=1
    )
    assert attempt_survives_run_failure(
        "WORKER_COMMAND_FAILED", worker_failure_occurrence_count=1
    )
    assert not attempt_survives_run_failure(
        "WORKER_FAILURE",
        worker_failure_occurrence_count=WORKER_FAILURE_REROUTE_AFTER,
    )
    assert not attempt_survives_run_failure(
        "AUTHORIZATION_FAILURE", worker_failure_occurrence_count=1
    )


def test_explicit_retire_ids_are_not_inferred() -> None:
    keep = uuid4()
    drop = uuid4()
    dispositions, explanations = classify_dispositions(
        task_ids=[keep, drop],
        statuses={keep: "CREATED", drop: "CREATED"},
        in_flight_ids=set(),
        completed_ids=set(),
        integrated_ids=set(),
        trigger="operator",
        retire_ids={drop},
    )
    assert dispositions[str(keep)] == "PRESERVE"
    assert dispositions[str(drop)] == "RETIRE"
    assert str(drop) in explanations


def test_unknown_failure_class_is_refused() -> None:
    with pytest.raises(DdeError) as captured:
        decide("NOT_A_CHAPTER_12_3_CLASS")
    assert captured.value.error_code == "POLICY_DENIED"


def test_wrong_product_integrated_node_is_revert() -> None:
    integrated = uuid4()
    open_task = uuid4()
    dispositions, explanations = classify_dispositions(
        task_ids=[integrated, open_task],
        statuses={integrated: "COMPLETED", open_task: "CREATED"},
        in_flight_ids=set(),
        completed_ids={integrated},
        integrated_ids={integrated},
        trigger="WRONG_PRODUCT",
    )
    assert dispositions[str(integrated)] == "REVERT"
    assert str(integrated) in explanations
    assert dispositions[str(open_task)] == "SUPERSEDE"


def test_operator_replan_quiesces_in_flight_and_preserves_the_rest() -> None:
    flying = uuid4()
    idle = uuid4()
    dispositions, _ = classify_dispositions(
        task_ids=[flying, idle],
        statuses={flying: "EXECUTING", idle: "CREATED"},
        in_flight_ids={flying},
        completed_ids=set(),
        integrated_ids=set(),
        trigger="operator",
    )
    assert dispositions[str(flying)] == "QUIESCE"
    assert dispositions[str(idle)] == "PRESERVE"
