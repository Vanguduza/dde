"""Chapter 18.6 removal-test rule (DDE-064)."""

from __future__ import annotations

from engine.readiness.inventory import (
    REMOVAL_CANDIDATES,
    S7_PRIOR_LANDINGS,
    missing_inventory_files,
)
from engine.readiness.removal import (
    KEEP,
    PROPOSE_EDR,
    RemovalMeasurement,
    evaluate_candidate,
)


def test_s7_and_removal_inventory_files_exist() -> None:
    assert missing_inventory_files() == []
    assert set(S7_PRIOR_LANDINGS) == {
        "experience_record",
        "routing_activation_gates",
        "context_activation_gates",
        "flight_lab",
        "chaos_suite",
        "dr_drill",
        "chapter_16_5_slos",
    }
    assert set(REMOVAL_CANDIDATES) == {
        "context_critic",
        "route_critic",
        "model_assisted_planning",
        "simulation_model",
        "retriever",
    }


def test_unmeasured_candidate_is_kept() -> None:
    verdict = evaluate_candidate(
        candidate="context_critic",
        measurement=RemovalMeasurement(None, None, None, None),
    )
    assert verdict.decision == KEEP
    assert verdict.reason == "unmeasured"


def test_outcome_drop_is_kept() -> None:
    verdict = evaluate_candidate(
        candidate="simulation_model",
        measurement=RemovalMeasurement(
            verified_success_now=10,
            overhead_tokens_now=1000,
            verified_success_if_removed=9,
            overhead_tokens_if_removed=100,
        ),
    )
    assert verdict.decision == KEEP
    assert verdict.reason == "verified_outcomes_would_drop"


def test_cost_increase_is_kept() -> None:
    verdict = evaluate_candidate(
        candidate="retriever",
        measurement=RemovalMeasurement(
            verified_success_now=10,
            overhead_tokens_now=1000,
            verified_success_if_removed=10,
            overhead_tokens_if_removed=2000,
        ),
    )
    assert verdict.decision == KEEP
    assert verdict.reason == "cost_per_verified_success_would_increase"


def test_justifying_measurement_proposes_edr_and_does_not_delete() -> None:
    verdict = evaluate_candidate(
        candidate="model_assisted_planning",
        measurement=RemovalMeasurement(
            verified_success_now=10,
            overhead_tokens_now=2000,
            verified_success_if_removed=10,
            overhead_tokens_if_removed=1000,
        ),
    )
    assert verdict.decision == PROPOSE_EDR
    assert verdict.reason == "measurement_justifies_edr"
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    assert (root / REMOVAL_CANDIDATES["model_assisted_planning"]).is_file()
