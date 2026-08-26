"""Schema tests for Stage 1 objects used by DDE-003 through DDE-007."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from engine.contracts.command_idempotency import CommandIdempotency
from engine.contracts.edr import Edr
from engine.contracts.event import Event
from engine.contracts.experience_record import ExperienceRecord
from engine.contracts.graph_amendment import GraphAmendment
from engine.contracts.mission import Mission
from engine.contracts.outbox import Outbox
from engine.contracts.requirement import Requirement
from engine.contracts.route_decision import RouteDecision
from engine.core.ids import uuid7


def _now() -> datetime:
    return datetime.now(UTC)


def test_requirement_rejects_unknown_fields() -> None:
    payload = {
        "requirement_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "slug": "REQ-AP-019",
        "statement": "Supplier credit limits are enforced",
        "constraints": [],
        "acceptance_conditions": ["limit is persisted"],
        "status": "approved",
        "created_at": _now(),
        "updated_at": _now(),
        "extra": True,
    }
    with pytest.raises(ValidationError):
        Requirement.model_validate(payload)


def test_edr_status_enum() -> None:
    with pytest.raises(ValidationError):
        Edr.model_validate(
            {
                "edr_id": uuid7(),
                "tenant_id": uuid7(),
                "project_id": uuid7(),
                "slug": "EDR-031",
                "context": "c",
                "alternatives": ["a"],
                "decision": "d",
                "rationale": "r",
                "consequences": [],
                "affected_requirement_slugs": [],
                "status": "rewritten",
                "created_at": _now(),
                "updated_at": _now(),
            }
        )


def test_mission_valid_created_status() -> None:
    mission = Mission.model_validate(
        {
            "mission_id": uuid7(),
            "tenant_id": uuid7(),
            "project_id": uuid7(),
            "slug": "MISSION-ERP-000421",
            "title": "Credit limits",
            "intent": "Implement supplier credit limits",
            "success_definition": "Oracle passes",
            "scope": ["engine"],
            "requirement_refs": ["REQ-AP-019"],
            "status": "CREATED",
            "autonomy_ceiling": 3,
            "lock_version": 1,
            "created_at": _now(),
            "updated_at": _now(),
        }
    )
    assert mission.status == "CREATED"


def _valid_event_payload() -> dict[str, object]:
    return {
        "event_id": uuid7(),
        "event_type": "EdrAccepted",
        "aggregate_type": "edr",
        "aggregate_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "sequence": 1,
        "occurred_at": _now(),
        "correlation_id": str(uuid7()),
        "payload": {"edr_id": "EDR-031"},
        "schema_version": "1",
        "created_at": _now(),
        "updated_at": _now(),
    }


def test_event_is_valid_with_only_required_fields() -> None:
    event = Event.model_validate(_valid_event_payload())
    assert event.mission_id is None
    assert event.causation_id is None


def test_event_rejects_missing_required_field() -> None:
    payload = _valid_event_payload()
    del payload["sequence"]
    with pytest.raises(ValidationError):
        Event.model_validate(payload)


def test_event_rejects_unknown_fields() -> None:
    payload = _valid_event_payload()
    payload["extra"] = True
    with pytest.raises(ValidationError):
        Event.model_validate(payload)


def _valid_outbox_payload() -> dict[str, object]:
    return {
        "outbox_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "event_id": uuid7(),
        "status": "pending",
        "payload": {"event_type": "EdrAccepted"},
        "created_at": _now(),
        "updated_at": _now(),
    }


def test_outbox_is_valid_with_only_required_fields() -> None:
    row = Outbox.model_validate(_valid_outbox_payload())
    assert row.published_at is None
    assert row.mission_id is None


def test_outbox_rejects_stale_status_value() -> None:
    payload = _valid_outbox_payload()
    payload["status"] = "delivered"
    with pytest.raises(ValidationError):
        Outbox.model_validate(payload)


def test_outbox_rejects_missing_required_field() -> None:
    payload = _valid_outbox_payload()
    del payload["payload"]
    with pytest.raises(ValidationError):
        Outbox.model_validate(payload)


def _valid_command_idempotency_payload() -> dict[str, object]:
    return {
        "command_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "idempotency_key": "accept-edr-031",
        "request_hash": "abc123",
        "status": "in_progress",
        "expires_at": _now(),
        "created_at": _now(),
        "updated_at": _now(),
    }


def test_command_idempotency_is_valid_with_only_required_fields() -> None:
    record = CommandIdempotency.model_validate(_valid_command_idempotency_payload())
    assert record.result is None


def test_command_idempotency_rejects_unknown_status() -> None:
    payload = _valid_command_idempotency_payload()
    payload["status"] = "abandoned"
    with pytest.raises(ValidationError):
        CommandIdempotency.model_validate(payload)


def test_command_idempotency_rejects_unknown_fields() -> None:
    payload = _valid_command_idempotency_payload()
    payload["extra"] = True
    with pytest.raises(ValidationError):
        CommandIdempotency.model_validate(payload)


def _valid_route_decision_payload() -> dict[str, object]:
    return {
        "decision_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "mission_id": uuid7(),
        "task_id": uuid7(),
        "candidates": [{"profile_id": "profile.general_implementation"}],
        "selected_worker_profile_id": "profile.general_implementation",
        "workload_class": "bulk_implementation",
        "required_capabilities": ["capability.repository"],
        "required_environment_class": "container-standard",
        "reason_codes": ["POLICY_PREFERRED"],
        "selection_source": "deterministic",
        "selection_propensity": 1.0,
        "fallback_plan": [],
        "escalation_plan": [],
        "policy_version": "deterministic-v1",
        "decision_hash": "abc123",
        "created_at": _now(),
        "updated_at": _now(),
    }


def test_route_decision_is_valid_with_only_required_fields() -> None:
    decision = RouteDecision.model_validate(_valid_route_decision_payload())
    assert decision.predicted_success is None
    assert decision.confidence is None


def test_route_decision_rejects_unknown_selection_source() -> None:
    payload = _valid_route_decision_payload()
    payload["selection_source"] = "guessed"
    with pytest.raises(ValidationError):
        RouteDecision.model_validate(payload)


def test_route_decision_rejects_missing_required_field() -> None:
    payload = _valid_route_decision_payload()
    del payload["decision_hash"]
    with pytest.raises(ValidationError):
        RouteDecision.model_validate(payload)


def test_route_decision_rejects_unknown_fields() -> None:
    payload = _valid_route_decision_payload()
    payload["extra"] = True
    with pytest.raises(ValidationError):
        RouteDecision.model_validate(payload)


def _valid_experience_record_payload() -> dict[str, object]:
    return {
        "experience_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "experience_origin": "real",
        "routing_policy_version": "deterministic-v1",
        "candidate_set_hash": "abc123",
        "selection_propensity": 1.0,
        "prediction_vector": {},
        "observed_outcome_vector": {"actual_verified_outcome": "PASSED"},
        "verification_confidence": 1.0,
        "failure_attribution": "none",
        "attribution_confidence": 1.0,
        "holdout_partition": "train",
        "promotion_evidence_refs": [],
        "eligible_for_routing_training": True,
        "eligibility_reasons": ["eligible"],
        "down_weighted": False,
        "promotion_state": "unpromoted",
        "created_at": _now(),
        "updated_at": _now(),
        "verification_run_id": uuid7(),
    }


def test_experience_record_is_valid_with_required_fields() -> None:
    record = ExperienceRecord.model_validate(_valid_experience_record_payload())
    assert record.experience_origin == "real"
    assert record.promotion_state == "unpromoted"


def test_experience_record_rejects_unknown_fields() -> None:
    payload = _valid_experience_record_payload()
    payload["extra"] = True
    with pytest.raises(ValidationError):
        ExperienceRecord.model_validate(payload)


def test_experience_record_rejects_unknown_origin() -> None:
    payload = _valid_experience_record_payload()
    payload["experience_origin"] = "synthetic"
    with pytest.raises(ValidationError):
        ExperienceRecord.model_validate(payload)


def test_graph_amendment_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        GraphAmendment.model_validate(
            {
                "amendment_id": uuid7(),
                "graph_id": uuid7(),
                "proposed_by": "run:1",
                "amendment_type": "mutate_in_place",
                "justification": "no",
                "evidence_refs": [],
                "affected_task_ids": [],
                "requested_write_scope": [],
            }
        )


def _valid_learned_routing_policy_payload() -> dict[str, object]:
    return {
        "policy_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "learning_run_id": uuid7(),
        "fit_kind": "frozen_full_information",
        "policy_hash": "abc",
        "mapping": {"bulk_implementation": "profile.general_implementation"},
        "constant_policy_profile_id": "profile.general_implementation",
        "train_count": 10,
        "holdout_count": 2,
        "beats_constant_policy": True,
        "continued_update": False,
        "status": "fitted",
        "training_experience_ids": [],
        "fallback_robustness_demonstrated": True,
        "created_at": _now(),
        "updated_at": _now(),
    }


def test_learned_routing_policy_is_valid_and_rejects_unknown_fields() -> None:
    from engine.contracts.learned_routing_policy import LearnedRoutingPolicy

    policy = LearnedRoutingPolicy.model_validate(
        _valid_learned_routing_policy_payload()
    )
    assert policy.continued_update is False
    assert policy.fit_kind == "frozen_full_information"
    payload = _valid_learned_routing_policy_payload()
    payload["extra"] = True
    with pytest.raises(ValidationError):
        LearnedRoutingPolicy.model_validate(payload)


def test_routing_activation_state_rejects_unknown_mode() -> None:
    from engine.contracts.routing_activation_state import RoutingActivationState

    with pytest.raises(ValidationError):
        RoutingActivationState.model_validate(
            {
                "activation_id": uuid7(),
                "tenant_id": uuid7(),
                "project_id": uuid7(),
                "routing_mode": "bandit",
                "last_certified_mode": "deterministic",
                "canary_fraction": 0.05,
                "continued_update_enabled": False,
                "created_at": _now(),
                "updated_at": _now(),
            }
        )


def test_context_activation_state_rejects_unknown_mode() -> None:
    from engine.contracts.context_activation_state import ContextActivationState

    with pytest.raises(ValidationError):
        ContextActivationState.model_validate(
            {
                "activation_id": uuid7(),
                "tenant_id": uuid7(),
                "project_id": uuid7(),
                "context_mode": "bandit",
                "candidate_arm": "pull",
                "last_certified_mode": "certified_baseline",
                "last_certified_arm": "pull",
                "canary_fraction": 0.05,
                "created_at": _now(),
                "updated_at": _now(),
            }
        )
