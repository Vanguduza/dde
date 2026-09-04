"""Project Truth constitution and requirements engine."""

from __future__ import annotations

import pytest

from engine.core.errors import DdeError
from tests.support.harness import CONSTITUTION, build_harness


def test_constitution_publish_and_supersede() -> None:
    harness = build_harness()
    first = harness.truth.publish_constitution(
        tenant_id=harness.tenant_id,
        project_id=harness.project_id,
        body_markdown=CONSTITUTION,
    )
    assert first.status == "active"
    assert first.version == 1
    second = harness.truth.publish_constitution(
        tenant_id=harness.tenant_id,
        project_id=harness.project_id,
        body_markdown=CONSTITUTION + "\nUpdated.\n",
    )
    assert second.version == 2
    assert harness.truth_store.constitutions[first.version_id].status == "superseded"
    assert harness.truth_store.active_constitution(harness.project_id) == second


def test_constitution_requires_chapter_24_headings() -> None:
    harness = build_harness()
    with pytest.raises(DdeError) as captured:
        harness.truth.publish_constitution(
            tenant_id=harness.tenant_id,
            project_id=harness.project_id,
            body_markdown="# Empty\n",
        )
    assert captured.value.error_code == "POLICY_DENIED"


def test_requirement_draft_approve_and_slug_unique() -> None:
    harness = build_harness()
    draft = harness.truth.draft_requirement(
        tenant_id=harness.tenant_id,
        project_id=harness.project_id,
        slug="REQ-AP-019",
        statement="Supplier credit limits are enforced at posting time.",
        constraints=["Cannot exceed configured limit"],
        acceptance_conditions=["Posting above the limit is rejected"],
    )
    assert draft.status == "draft"
    approved = harness.truth.approve_requirement(draft.requirement_id)
    assert approved.status == "approved"
    with pytest.raises(DdeError) as captured:
        harness.truth.draft_requirement(
            tenant_id=harness.tenant_id,
            project_id=harness.project_id,
            slug="REQ-AP-019",
            statement="Duplicate slug",
            constraints=[],
            acceptance_conditions=["x"],
        )
    assert captured.value.error_code == "VERSION_CONFLICT"


def test_requirement_without_acceptance_conditions_is_rejected() -> None:
    harness = build_harness()
    with pytest.raises(DdeError):
        harness.truth.draft_requirement(
            tenant_id=harness.tenant_id,
            project_id=harness.project_id,
            slug="REQ-BAD",
            statement="Something",
            constraints=[],
            acceptance_conditions=[],
        )
