"""Chapter 13.1–13.4 / 13.7 pure policy tests (no I/O)."""

from __future__ import annotations

import pytest

from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.governance.config import RuntimeFlags, validate_configuration
from engine.governance.hashing import approval_scope_hash
from engine.governance.types import STANDING_FORBIDDEN_TYPES


def test_scope_hash_changes_when_the_plan_changes() -> None:
    mission_id = uuid7()
    base = approval_scope_hash(
        approval_type="scope_widening",
        mission_id=mission_id,
        payload={"paths": ["engine/truth"]},
    )
    changed = approval_scope_hash(
        approval_type="scope_widening",
        mission_id=mission_id,
        payload={"paths": ["secret/other"]},
    )
    assert base != changed


def test_standing_forbidden_types_match_chapter_13_2() -> None:
    assert "irreversible_effect" in STANDING_FORBIDDEN_TYPES
    assert "production_change" in STANDING_FORBIDDEN_TYPES


def test_config_validation_rejects_audit_only_outside_development() -> None:
    with pytest.raises(DdeError) as captured:
        validate_configuration(
            RuntimeFlags(
                environment_class="production",
                capability_enforcement_mode="audit_only",
            )
        )
    assert captured.value.error_code == "POLICY_DENIED"


def test_config_validation_allows_audit_only_in_development() -> None:
    validate_configuration(
        RuntimeFlags(
            environment_class="development",
            capability_enforcement_mode="audit_only",
        )
    )


def test_config_validation_rejects_merge_queue_concurrency_above_one() -> None:
    with pytest.raises(DdeError):
        validate_configuration(
            RuntimeFlags(environment_class="staging", merge_queue_concurrency=2)
        )
