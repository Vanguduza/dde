"""Schema tests (Chapter 19.1) for the objects DDE-031 introduces:
`ContextConflict` (Chapter 5.6) and `ContextCriticFinding` (Chapter 5.9).

Written before `engine/contracts/context_conflict.py` /
`engine/contracts/context_critic_finding.py` exist -- these imports fail
until `python -m scripts.generate_contracts` regenerates them from the
`schemas/objects/*.json` this mission adds.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from engine.contracts.context_conflict import ContextConflict
from engine.contracts.context_critic_finding import ContextCriticFinding
from engine.core.ids import uuid7


def _now() -> datetime:
    return datetime.now(UTC)


def _valid_conflict_payload() -> dict[str, object]:
    now = _now()
    return {
        "conflict_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "mission_id": uuid7(),
        "task_id": uuid7(),
        "package_id": uuid7(),
        "item_a_key": "edr:EDR-1",
        "item_a_authority_rank": 4,
        "item_b_key": "edr:EDR-2",
        "item_b_authority_rank": 4,
        "contradiction_type": "overlapping_accepted_edrs",
        "affected_success_criteria": ["REQ-1"],
        "status": "open",
        "resolution_method": None,
        "resolved_at": None,
        "created_at": now,
        "updated_at": now,
    }


def test_context_conflict_is_valid_with_required_fields() -> None:
    conflict = ContextConflict.model_validate(_valid_conflict_payload())
    assert conflict.status == "open"
    assert conflict.contradiction_type == "overlapping_accepted_edrs"


def test_context_conflict_rejects_missing_required_field() -> None:
    payload = _valid_conflict_payload()
    del payload["affected_success_criteria"]
    with pytest.raises(ValidationError):
        ContextConflict.model_validate(payload)


def test_context_conflict_rejects_unknown_contradiction_type() -> None:
    payload = _valid_conflict_payload()
    payload["contradiction_type"] = "vibes"
    with pytest.raises(ValidationError):
        ContextConflict.model_validate(payload)


def test_context_conflict_rejects_unknown_fields() -> None:
    payload = _valid_conflict_payload()
    payload["notes"] = "looks fine"
    with pytest.raises(ValidationError):
        ContextConflict.model_validate(payload)


def _valid_finding_payload() -> dict[str, object]:
    now = _now()
    return {
        "finding_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "mission_id": uuid7(),
        "task_id": uuid7(),
        "package_id": uuid7(),
        "trigger_reasons": ["risk_class_high_or_above"],
        "confidence": 0.42,
        "action": "raised_finding",
        "outcome_summary": "No additional retrieval was available.",
        "requires_human_review": True,
        "reviewed": False,
        "reviewed_at": None,
        "cost_tokens_estimate": 12,
        "created_at": now,
        "updated_at": now,
    }


def test_context_critic_finding_is_valid_with_required_fields() -> None:
    finding = ContextCriticFinding.model_validate(_valid_finding_payload())
    assert finding.action == "raised_finding"
    assert finding.requires_human_review is True


def test_context_critic_finding_rejects_unknown_action() -> None:
    payload = _valid_finding_payload()
    payload["action"] = "auto_approved"
    with pytest.raises(ValidationError):
        ContextCriticFinding.model_validate(payload)


def test_context_critic_finding_rejects_unknown_fields() -> None:
    payload = _valid_finding_payload()
    payload["notes"] = "looks fine"
    with pytest.raises(ValidationError):
        ContextCriticFinding.model_validate(payload)
