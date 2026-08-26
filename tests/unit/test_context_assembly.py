"""Chapter 5.7 budget/eviction: write-scope and authority evidence must
never be evicted; only lower-tier code evidence is evictable, and an
un-evictable overflow returns `ContextBudgetExceeded` rather than raising."""

from __future__ import annotations

from datetime import UTC, datetime

from engine.context.assembly import assemble
from engine.context.model import (
    AUTHORITY_RANK_CODE,
    ContextBudgetExceeded,
    ContextItem,
    FusedItem,
)
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
        requirement_refs=[],
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


def _fused(
    key: str,
    *,
    content: str,
    write_scope_match: bool = False,
    retriever: str = "lexical",
    categories: tuple[str, ...] = ("impacted_code_and_deps",),
    score: float = 1.0,
) -> FusedItem:
    item = ContextItem(
        retriever=retriever,
        key=key,
        categories=categories,
        authority_rank=AUTHORITY_RANK_CODE,
        rank_in_retriever=1,
        relevance=1.0,
        write_scope_match=write_scope_match,
        content=content,
        source_path=None,
    )
    return FusedItem(item=item, fused_score=score, contributing_retrievers=(retriever,))


def test_assemble_always_includes_success_criteria_and_write_scope_items() -> None:
    task = _task()
    write_scope_item = _fused(
        "file:pkg/mod.py", content="x" * 40, write_scope_match=True
    )

    result = assemble(task, [write_scope_item], budget_tokens=8000)

    assert not isinstance(result, ContextBudgetExceeded)
    keys = {fused.item.key for fused in result.included}
    assert "success_criteria" in keys
    assert "file:pkg/mod.py" in keys
    assert result.evicted == ()


def test_assemble_evicts_lowest_priority_items_first_under_a_tight_budget() -> None:
    task = _task()
    write_scope_item = _fused(
        "file:pkg/mod.py", content="w" * 40, write_scope_match=True
    )
    other_code_low = _fused("file:sibling_low.py", content="s" * 4000, score=0.1)
    other_code_high = _fused("file:sibling_high.py", content="s" * 40, score=0.9)

    # Budget fits the unevictable items plus the small high-score item, but
    # not the large low-score sibling file.
    result = assemble(
        task,
        [write_scope_item, other_code_low, other_code_high],
        budget_tokens=40,
    )

    assert not isinstance(result, ContextBudgetExceeded)
    included_keys = {fused.item.key for fused in result.included}
    evicted_keys = {fused.item.key for fused in result.evicted}
    assert "file:pkg/mod.py" in included_keys  # write scope: never evicted
    assert "success_criteria" in included_keys  # requirements tier: never evicted
    assert "file:sibling_low.py" in evicted_keys


def test_assemble_returns_budget_exceeded_when_unevictable_alone_overflows() -> None:
    task = _task(success_criteria=["c" * 5000])

    result = assemble(task, [], budget_tokens=10)

    assert isinstance(result, ContextBudgetExceeded)
    assert result.task_id == task.task_id
    assert result.budget_tokens == 10
    assert result.required_tokens > 10


def test_push_arm_makes_architecture_evidence_unevictable() -> None:
    """Pull evicts architecture under a tight budget; push injects it
    up front and overflows rather than silently dropping it."""
    task = _task()
    architecture = _fused(
        "file:arch.md",
        content="a" * 4000,
        categories=("architecture_constraints",),
        score=0.1,
    )
    pull = assemble(task, [architecture], budget_tokens=80)
    push = assemble(task, [architecture], budget_tokens=80, policy_arm="push")

    assert not isinstance(pull, ContextBudgetExceeded)
    evicted_keys = {fused.item.key for fused in pull.evicted}
    assert "file:arch.md" in evicted_keys
    assert isinstance(push, ContextBudgetExceeded)
