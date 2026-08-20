"""Chapter 3.10 immutable-definition hashing: `assembly_hash` is stable
for identical definition inputs and excludes lifecycle columns entirely
(they are simply not parameters to the function)."""

from __future__ import annotations

from engine.context.hashing import assembly_hash
from engine.context.model import AUTHORITY_RANK_CODE, ContextItem, FusedItem
from engine.core.ids import uuid7


def _fused(key: str, content: str = "content") -> FusedItem:
    item = ContextItem(
        retriever="lexical",
        key=key,
        categories=("impacted_code_and_deps",),
        authority_rank=AUTHORITY_RANK_CODE,
        rank_in_retriever=1,
        relevance=1.0,
        write_scope_match=False,
        content=content,
        source_path=None,
    )
    return FusedItem(item=item, fused_score=1.0, contributing_retrievers=("lexical",))


def test_assembly_hash_is_stable_for_identical_inputs() -> None:
    task_id = uuid7()
    tenant_id = uuid7()
    project_id = uuid7()
    mission_id = uuid7()
    coverage = {"authoritative_requirements": "satisfied"}
    items = (_fused("file:a.py"), _fused("file:b.py"))

    first = assembly_hash(
        task_id=task_id,
        tenant_id=tenant_id,
        project_id=project_id,
        mission_id=mission_id,
        index_version="abc123",
        index_lag_commits=0,
        coverage=coverage,
        included_items=items,
    )
    second = assembly_hash(
        task_id=task_id,
        tenant_id=tenant_id,
        project_id=project_id,
        mission_id=mission_id,
        index_version="abc123",
        index_lag_commits=0,
        coverage=coverage,
        included_items=items,
    )

    assert first == second


def test_assembly_hash_is_order_independent_over_included_items() -> None:
    """Item ordering is an artifact of fusion/assembly, not part of the
    definition — hashing sorts internally so recompiling with the same
    evidence in a different order still yields the same hash."""
    task_id, tenant_id, project_id, mission_id = uuid7(), uuid7(), uuid7(), uuid7()
    coverage = {"authoritative_requirements": "satisfied"}
    a, b = _fused("file:a.py"), _fused("file:b.py")

    forward = assembly_hash(
        task_id=task_id,
        tenant_id=tenant_id,
        project_id=project_id,
        mission_id=mission_id,
        index_version="abc123",
        index_lag_commits=0,
        coverage=coverage,
        included_items=(a, b),
    )
    reversed_order = assembly_hash(
        task_id=task_id,
        tenant_id=tenant_id,
        project_id=project_id,
        mission_id=mission_id,
        index_version="abc123",
        index_lag_commits=0,
        coverage=coverage,
        included_items=(b, a),
    )

    assert forward == reversed_order


def test_assembly_hash_changes_when_content_changes() -> None:
    task_id, tenant_id, project_id, mission_id = uuid7(), uuid7(), uuid7(), uuid7()
    coverage = {"authoritative_requirements": "satisfied"}

    original = assembly_hash(
        task_id=task_id,
        tenant_id=tenant_id,
        project_id=project_id,
        mission_id=mission_id,
        index_version="abc123",
        index_lag_commits=0,
        coverage=coverage,
        included_items=(_fused("file:a.py", content="original"),),
    )
    changed = assembly_hash(
        task_id=task_id,
        tenant_id=tenant_id,
        project_id=project_id,
        mission_id=mission_id,
        index_version="abc123",
        index_lag_commits=0,
        coverage=coverage,
        included_items=(_fused("file:a.py", content="changed"),),
    )

    assert original != changed


def test_assembly_hash_changes_when_coverage_changes() -> None:
    task_id, tenant_id, project_id, mission_id = uuid7(), uuid7(), uuid7(), uuid7()
    items = (_fused("file:a.py"),)

    satisfied = assembly_hash(
        task_id=task_id,
        tenant_id=tenant_id,
        project_id=project_id,
        mission_id=mission_id,
        index_version="abc123",
        index_lag_commits=0,
        coverage={"authoritative_requirements": "satisfied"},
        included_items=items,
    )
    missing = assembly_hash(
        task_id=task_id,
        tenant_id=tenant_id,
        project_id=project_id,
        mission_id=mission_id,
        index_version="abc123",
        index_lag_commits=0,
        coverage={"authoritative_requirements": "missing"},
        included_items=items,
    )

    assert satisfied != missing
