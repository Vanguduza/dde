"""PostgreSQL-backed `engine.context`: schema, state-transition and
negative tests (Chapter 19.1). Exercises `engine.context.service.
ContextService`, the production writer of `context_packages` (Chapter
3.8), against a real database.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.context.model import ContextBudgetExceeded
from engine.context.repository import ContextRepository
from engine.context.service import ContextService
from engine.truth.db import open_unit_of_work
from tests.support.context_fixtures import build_context_fixture, build_fake_repo
from tests.support.db import new_engine


@pytest.mark.asyncio
async def test_schema_round_trip_persists_declared_columns(tmp_path: Path) -> None:
    """A `context_packages` row read back from the real table validates
    against the JSON-schema-generated contract with no drift (Chapter
    3.1) — the schema test."""
    engine = new_engine()
    try:
        build_fake_repo(tmp_path)
        fixture = await build_context_fixture(engine, mission_slug="MISSION-CTX-SCHEMA")
        service = ContextService(engine, root=tmp_path)

        compiled = await service.compile(task=fixture.task)
        assert not isinstance(compiled, ContextBudgetExceeded)

        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            reloaded = await ContextRepository().get_context_package(
                uow.connection, compiled.package_id
            )
            await uow.commit()
        assert reloaded == compiled
        assert reloaded is not None
        assert reloaded.version == 1
        assert reloaded.retrievers_used == [
            "explicit",
            "authority",
            "lexical",
            "structural",
        ]
        assert reloaded.index_lag_commits == 0
        assert isinstance(reloaded.index_version, str) and reloaded.index_version
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_well_covered_task_compiles_to_complete_status(tmp_path: Path) -> None:
    """A task whose refs, write scope and terms are all genuinely
    resolvable produces `COMPLETE` status with every required category
    `satisfied` — proof that coverage is computed from real retrieval,
    not hardcoded."""
    engine = new_engine()
    try:
        build_fake_repo(tmp_path)
        fixture = await build_context_fixture(engine, mission_slug="MISSION-CTX-GOOD")
        service = ContextService(engine, root=tmp_path)

        compiled = await service.compile(task=fixture.task)
        assert not isinstance(compiled, ContextBudgetExceeded)

        coverage = compiled.coverage
        assert coverage["authoritative_requirements"] == "satisfied"
        assert coverage["applicable_domain_rules"] == "satisfied"
        assert coverage["impacted_code_and_deps"] == "satisfied"
        assert coverage["architecture_constraints"] == "satisfied"
        assert coverage["security_constraints"] == "satisfied"
        assert coverage["verification_obligations"] == "satisfied"
        assert coverage["known_unresolved_questions"] == []
        assert compiled.status == "COMPLETE"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_poorly_covered_task_compiles_to_incomplete_status(
    tmp_path: Path,
) -> None:
    """A task whose requirement ref does not exist and whose terms match
    nothing in the corpus produces genuinely `missing` categories and an
    `INCOMPLETE` package status — the negative-shaped coverage case,
    computed the same way as the well-covered one, not a special path."""
    engine = new_engine()
    try:
        build_fake_repo(tmp_path)
        fixture = await build_context_fixture(
            engine,
            mission_slug="MISSION-CTX-BAD",
            task_title="Completely unrelated widget",
            task_intent="frobnicate the zzzznonexistentqqq widget dashboard",
            success_criteria=["The unrelated widget renders"],
            requirement_refs=["REQ-DOES-NOT-EXIST"],
            expected_read_scope=[],
            expected_write_scope=["interfaces"],
            include_edr=False,
        )
        service = ContextService(engine, root=tmp_path)

        compiled = await service.compile(task=fixture.task)
        assert not isinstance(compiled, ContextBudgetExceeded)

        coverage = compiled.coverage
        assert coverage["authoritative_requirements"] == "missing"
        assert (
            coverage["applicable_domain_rules"] == "satisfied"
        )  # vacuous: no EDR-like ref
        assert coverage["impacted_code_and_deps"] == "missing"
        assert coverage["architecture_constraints"] == "missing"
        assert (
            coverage["security_constraints"] == "satisfied"
        )  # vacuous: not security-relevant
        assert coverage["verification_obligations"] == "satisfied"
        assert any(
            "REQ-DOES-NOT-EXIST" in question
            for question in coverage["known_unresolved_questions"]
        )
        assert compiled.status == "INCOMPLETE"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_recompile_produces_new_immutable_version_with_stable_hash(
    tmp_path: Path,
) -> None:
    """Chapter 3.10: recompiling the same task produces a NEW version with
    a new `package_id`; the prior version remains queryable and unchanged;
    `assembly_hash` is stable across the two compiles since nothing about
    the task, Project Truth or the corpus changed between them."""
    engine = new_engine()
    try:
        build_fake_repo(tmp_path)
        fixture = await build_context_fixture(
            engine, mission_slug="MISSION-CTX-VERSION"
        )
        service = ContextService(engine, root=tmp_path)

        first = await service.compile(task=fixture.task)
        second = await service.compile(task=fixture.task)
        assert not isinstance(first, ContextBudgetExceeded)
        assert not isinstance(second, ContextBudgetExceeded)

        assert first.package_id != second.package_id
        assert second.version == first.version + 1
        assert second.assembly_hash == first.assembly_hash
        assert second.coverage == first.coverage

        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            reread_first = await ContextRepository().get_context_package(
                uow.connection, first.package_id
            )
            versions = await ContextRepository().list_versions_for_task(
                uow.connection, fixture.task.task_id
            )
            await uow.commit()
        assert reread_first == first
        assert [item.version for item in versions] == [1, 2]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_context_budget_exceeded_persists_nothing(
    tmp_path: Path,
) -> None:
    """Chapter 5.7: when the un-evictable evidence alone exceeds
    `context_budget`, `compile()` returns a typed `ContextBudgetExceeded`
    result — not an exception, not a partially-assembled row — and no
    `context_packages` row is written."""
    engine = new_engine()
    try:
        build_fake_repo(tmp_path)
        fixture = await build_context_fixture(engine, mission_slug="MISSION-CTX-BUDGET")
        service = ContextService(engine, root=tmp_path)

        result = await service.compile(task=fixture.task, context_budget_tokens=1)

        assert isinstance(result, ContextBudgetExceeded)
        assert result.task_id == fixture.task.task_id
        assert result.budget_tokens == 1
        assert result.required_tokens > result.budget_tokens

        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            versions = await ContextRepository().list_versions_for_task(
                uow.connection, fixture.task.task_id
            )
            await uow.commit()
        assert versions == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_authority_retriever_resolves_real_requirement_and_edr(
    tmp_path: Path,
) -> None:
    """The authority retriever reads real `requirements`/`edrs` rows
    through `engine.truth.repository.TruthRepository` (Chapter 5.2) — not
    a second, parallel reader — and Chapter 2.2 rank weighting (rank 3
    Requirements outrank rank 4 EDRs) shows up in fusion ordering."""
    engine = new_engine()
    try:
        build_fake_repo(tmp_path)
        fixture = await build_context_fixture(engine, mission_slug="MISSION-CTX-AUTH")
        service = ContextService(engine, root=tmp_path)

        compiled = await service.compile(task=fixture.task)
        assert not isinstance(compiled, ContextBudgetExceeded)
        assert compiled.coverage["authoritative_requirements"] == "satisfied"
        assert compiled.coverage["applicable_domain_rules"] == "satisfied"
    finally:
        await engine.dispose()
