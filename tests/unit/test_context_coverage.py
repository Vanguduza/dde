"""Chapter 5.8 coverage contract: statuses reflect genuine retrieved/
assembled evidence, never a hardcoded answer."""

from __future__ import annotations

from datetime import UTC, datetime

from engine.context.assembly import assemble
from engine.context.coverage import compute_coverage
from engine.context.discovery import DiscoveryResult
from engine.context.fusion import fuse
from engine.context.model import AUTHORITY_RANK_CODE, ContextBudgetExceeded, ContextItem
from engine.context.retrievers.authority import AuthorityResult
from engine.contracts.requirement import Requirement
from engine.contracts.task import Task
from engine.core.ids import uuid7


def _task(**overrides: object) -> Task:
    now = datetime.now(UTC)
    defaults: dict[str, object] = dict(
        task_id=uuid7(),
        tenant_id=uuid7(),
        project_id=uuid7(),
        mission_id=uuid7(),
        graph_id=uuid7(),
        title="t",
        intent="i",
        task_class="verification",
        requirement_refs=["REQ-1"],
        feature_refs=[],
        success_criteria=["some criterion"],
        expected_write_scope=["pkg"],
        expected_read_scope=[],
        blast_radius="local",
        risk_class="low",
        estimated_effort="s",
        autonomy_ceiling=2,
        requires_approval=False,
        status="CREATED",
        lock_version=1,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return Task.model_validate(defaults)


def _requirement(status: str = "approved") -> Requirement:
    now = datetime.now(UTC)
    return Requirement(
        requirement_id=uuid7(),
        tenant_id=uuid7(),
        project_id=uuid7(),
        slug="REQ-1",
        statement="Do the thing",
        constraints=[],
        acceptance_conditions=["it works"],
        status=status,  # type: ignore[arg-type]
        created_at=now,
        updated_at=now,
    )


def _discovery(task: Task) -> DiscoveryResult:
    return DiscoveryResult(
        requirement_refs=tuple(task.requirement_refs),
        feature_refs=tuple(task.feature_refs),
        expected_read_scope=tuple(task.expected_read_scope),
        expected_write_scope=tuple(task.expected_write_scope),
        resolved_paths=(),
        unresolved_paths=(),
    )


def _code_item(*, source_path: str, categories: tuple[str, ...]) -> ContextItem:
    return ContextItem(
        retriever="lexical",
        key=f"file:{source_path}",
        categories=categories,
        authority_rank=AUTHORITY_RANK_CODE,
        rank_in_retriever=1,
        relevance=1.0,
        write_scope_match=True,
        content="content",
        source_path=source_path,
    )


def test_coverage_satisfied_when_write_scope_and_requirement_and_criteria_present() -> (
    None
):
    task = _task()
    requirement = _requirement(status="approved")
    authority_result = AuthorityResult(
        items=[],
        resolved_requirements=[requirement],
        resolved_edrs=[],
        unresolved_refs=[],
    )
    write_item = _code_item(
        source_path="pkg/mod.py", categories=("impacted_code_and_deps",)
    )
    architecture_item = _code_item(
        source_path="AGENTS.md", categories=("architecture_constraints",)
    )
    fused = fuse({"lexical": [write_item], "structural": [architecture_item]})
    assembled = assemble(task, fused, budget_tokens=8000)
    assert not isinstance(assembled, ContextBudgetExceeded)

    coverage = compute_coverage(
        task, _discovery(task), authority_result, fused, assembled
    )

    assert coverage.authoritative_requirements == "satisfied"
    assert coverage.impacted_code_and_deps == "satisfied"
    assert coverage.architecture_constraints == "satisfied"
    assert coverage.verification_obligations == "satisfied"
    assert coverage.known_unresolved_questions == ()


def test_coverage_missing_when_requirement_ref_does_not_resolve() -> None:
    task = _task(requirement_refs=["REQ-GHOST"])
    authority_result = AuthorityResult(
        items=[],
        resolved_requirements=[],
        resolved_edrs=[],
        unresolved_refs=["REQ-GHOST"],
    )
    fused = fuse({})
    assembled = assemble(task, fused, budget_tokens=8000)
    assert not isinstance(assembled, ContextBudgetExceeded)

    coverage = compute_coverage(
        task, _discovery(task), authority_result, fused, assembled
    )

    assert coverage.authoritative_requirements == "missing"
    assert any(
        "REQ-GHOST" in question for question in coverage.known_unresolved_questions
    )


def test_coverage_partial_when_requirement_resolved_but_not_approved() -> None:
    task = _task()
    requirement = _requirement(status="draft")
    authority_result = AuthorityResult(
        items=[],
        resolved_requirements=[requirement],
        resolved_edrs=[],
        unresolved_refs=[],
    )
    fused = fuse({})
    assembled = assemble(task, fused, budget_tokens=8000)
    assert not isinstance(assembled, ContextBudgetExceeded)

    coverage = compute_coverage(
        task, _discovery(task), authority_result, fused, assembled
    )

    assert coverage.authoritative_requirements == "partial"


def test_coverage_missing_impacted_code_when_write_scope_has_no_evidence() -> None:
    task = _task()
    requirement = _requirement(status="approved")
    authority_result = AuthorityResult(
        items=[],
        resolved_requirements=[requirement],
        resolved_edrs=[],
        unresolved_refs=[],
    )
    fused = fuse({})
    assembled = assemble(task, fused, budget_tokens=8000)
    assert not isinstance(assembled, ContextBudgetExceeded)

    coverage = compute_coverage(
        task, _discovery(task), authority_result, fused, assembled
    )

    assert coverage.impacted_code_and_deps == "missing"
    assert any("pkg" in question for question in coverage.known_unresolved_questions)


def test_coverage_satisfied_domain_rules_vacuously_when_no_edr_refs_declared() -> None:
    task = _task(requirement_refs=["REQ-1"])
    authority_result = AuthorityResult(
        items=[],
        resolved_requirements=[_requirement()],
        resolved_edrs=[],
        unresolved_refs=[],
    )
    fused = fuse({})
    assembled = assemble(task, fused, budget_tokens=8000)
    assert not isinstance(assembled, ContextBudgetExceeded)

    coverage = compute_coverage(
        task, _discovery(task), authority_result, fused, assembled
    )

    assert coverage.applicable_domain_rules == "satisfied"


def test_coverage_missing_when_edr_ref_does_not_resolve() -> None:
    task = _task(requirement_refs=["EDR-1"])
    authority_result = AuthorityResult(
        items=[], resolved_requirements=[], resolved_edrs=[], unresolved_refs=["EDR-1"]
    )
    fused = fuse({})
    assembled = assemble(task, fused, budget_tokens=8000)
    assert not isinstance(assembled, ContextBudgetExceeded)

    coverage = compute_coverage(
        task, _discovery(task), authority_result, fused, assembled
    )

    assert coverage.applicable_domain_rules == "missing"


def test_coverage_security_satisfied_when_task_is_not_security_relevant() -> None:
    task = _task(title="Add a button", intent="Add a UI button", success_criteria=["c"])
    authority_result = AuthorityResult(
        items=[],
        resolved_requirements=[_requirement()],
        resolved_edrs=[],
        unresolved_refs=[],
    )
    fused = fuse({})
    assembled = assemble(task, fused, budget_tokens=8000)
    assert not isinstance(assembled, ContextBudgetExceeded)

    coverage = compute_coverage(
        task, _discovery(task), authority_result, fused, assembled
    )

    assert coverage.security_constraints == "satisfied"


def test_coverage_security_missing_when_relevant_but_no_evidence_found() -> None:
    task = _task(
        title="Rotate credential",
        intent="Rotate the RLS tenant credential safely",
        success_criteria=["credential is rotated"],
    )
    authority_result = AuthorityResult(
        items=[],
        resolved_requirements=[_requirement()],
        resolved_edrs=[],
        unresolved_refs=[],
    )
    fused = fuse({})
    assembled = assemble(task, fused, budget_tokens=8000)
    assert not isinstance(assembled, ContextBudgetExceeded)

    coverage = compute_coverage(
        task, _discovery(task), authority_result, fused, assembled
    )

    assert coverage.security_constraints == "missing"


def test_coverage_verification_obligations_missing_when_no_success_criteria() -> None:
    task = _task(success_criteria=[])
    authority_result = AuthorityResult(
        items=[],
        resolved_requirements=[_requirement()],
        resolved_edrs=[],
        unresolved_refs=[],
    )
    fused = fuse({})
    assembled = assemble(task, fused, budget_tokens=8000)
    assert not isinstance(assembled, ContextBudgetExceeded)

    coverage = compute_coverage(
        task, _discovery(task), authority_result, fused, assembled
    )

    assert coverage.verification_obligations == "missing"


def test_coverage_flags_unresolved_expected_read_scope_paths() -> None:
    task = _task(expected_read_scope=["missing_file.py"])
    authority_result = AuthorityResult(
        items=[],
        resolved_requirements=[_requirement()],
        resolved_edrs=[],
        unresolved_refs=[],
    )
    discovery = DiscoveryResult(
        requirement_refs=tuple(task.requirement_refs),
        feature_refs=tuple(task.feature_refs),
        expected_read_scope=tuple(task.expected_read_scope),
        expected_write_scope=tuple(task.expected_write_scope),
        resolved_paths=(),
        unresolved_paths=("missing_file.py",),
    )
    fused = fuse({})
    assembled = assemble(task, fused, budget_tokens=8000)
    assert not isinstance(assembled, ContextBudgetExceeded)

    coverage = compute_coverage(task, discovery, authority_result, fused, assembled)

    assert any(
        "missing_file.py" in question
        for question in coverage.known_unresolved_questions
    )
