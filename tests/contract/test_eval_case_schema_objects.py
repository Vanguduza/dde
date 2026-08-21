"""Schema tests (Chapter 19.1) for the objects DDE-031 introduces:
`EvalCase` and `PromotionGateRun` (`engine.context`, Chapter 5.13).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from engine.contracts.eval_case import EvalCase
from engine.contracts.promotion_gate_run import PromotionGateRun
from engine.core.ids import uuid7


def _now() -> datetime:
    return datetime.now(UTC)


def _valid_eval_case_payload() -> dict[str, object]:
    now = _now()
    return {
        "eval_case_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "source_mission_id": uuid7(),
        "source_task_id": uuid7(),
        "source_proposal_id": uuid7(),
        "task_class": "verification",
        "is_adversarial": False,
        "required_refs": ["engine/context/service.py", "REQ-CTX-1"],
        "status": "draft",
        "frozen_version": None,
        "retired_reason": None,
        "created_at": now,
        "updated_at": now,
    }


def test_eval_case_is_valid_with_required_fields() -> None:
    case = EvalCase.model_validate(_valid_eval_case_payload())
    assert case.status == "draft"
    assert case.frozen_version is None


def test_eval_case_rejects_missing_required_field() -> None:
    payload = _valid_eval_case_payload()
    del payload["required_refs"]
    with pytest.raises(ValidationError):
        EvalCase.model_validate(payload)


def test_eval_case_rejects_unknown_status() -> None:
    payload = _valid_eval_case_payload()
    payload["status"] = "active"
    with pytest.raises(ValidationError):
        EvalCase.model_validate(payload)


def test_eval_case_rejects_unknown_fields() -> None:
    payload = _valid_eval_case_payload()
    payload["priority"] = "high"
    with pytest.raises(ValidationError):
        EvalCase.model_validate(payload)


def _valid_promotion_gate_run_payload() -> dict[str, object]:
    now = _now()
    return {
        "run_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "idempotency_key": "semantic-retrieval-2026-08",
        "candidate_label": "semantic_retrieval_enabled",
        "status": "PENDING",
        "corpus_size": 0,
        "task_class_count": 0,
        "adversarial_count": 0,
        "decision": None,
        "gate_results": {},
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }


def test_promotion_gate_run_is_valid_with_required_fields() -> None:
    run = PromotionGateRun.model_validate(_valid_promotion_gate_run_payload())
    assert run.status == "PENDING"
    assert run.decision is None


def test_promotion_gate_run_rejects_full_pass_decision() -> None:
    """Chapter 5.13 lists five promotion gates; this deployment computes
    only one (critical_coverage -- EDR-0003). The decision vocabulary must
    never contain a bare PASS that could be mistaken for full promotion."""
    payload = _valid_promotion_gate_run_payload()
    payload["decision"] = "PASS"
    with pytest.raises(ValidationError):
        PromotionGateRun.model_validate(payload)


def test_promotion_gate_run_rejects_unknown_fields() -> None:
    payload = _valid_promotion_gate_run_payload()
    payload["notes"] = "looks fine"
    with pytest.raises(ValidationError):
        PromotionGateRun.model_validate(payload)
