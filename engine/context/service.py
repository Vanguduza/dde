"""Production Context Intelligence — the sole writer of `context_packages`
rows in PostgreSQL (Chapter 2.6, 3.5, 3.8, 5.1).

`ContextService.compile()` runs the Stage 1 slice of the Chapter 5.1
pipeline end to end: Discovery -> the four Stage 1 retrievers (explicit,
authority, lexical, structural; Chapter 5.2) -> reciprocal rank fusion
with authority-rank weighting (Chapter 5.3) -> budget-aware assembly with
Chapter 5.7's eviction priority order -> the Chapter 5.8 coverage
contract -> a versioned, hashed `ContextPackage` row (Chapter 3.10).

Deliberately out of Stage 1 scope, per the mission brief: semantic
retrieval (needs pgvector/embeddings), dependency/graph/temporal/
documentation/visual retrievers, the Context Critic (needs risk/blast-
radius/confidence signals this slice does not compute), conflict
adjudication (needs a genuine rank<=6 contradiction to trigger — no
fixture here manufactures one), index lifecycle/backfill (only the
`index_version`/`index_lag_commits` fields are populated, with the
current commit SHA and `0` respectively), just-in-time expansion (needs
worker runs, Chapter 5.12/DDE-011+), and the knowledge-graph derived/
asserted split (Chapter 5.10/DDE-033).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.context.assembly import DEFAULT_CONTEXT_BUDGET_TOKENS, assemble
from engine.context.coverage import compute_coverage
from engine.context.discovery import discover
from engine.context.fusion import fuse
from engine.context.hashing import assembly_hash
from engine.context.model import ContextBudgetExceeded, ContextItem
from engine.context.repo import current_commit_sha, repo_root
from engine.context.repository import ContextRepository
from engine.context.retrievers import authority, explicit, lexical, structural
from engine.contracts.context_package import ContextPackage
from engine.contracts.task import Task
from engine.core.clock import Clock, SystemClock
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")

REQUIRED_COVERAGE_CATEGORIES = (
    "authoritative_requirements",
    "applicable_domain_rules",
    "impacted_code_and_deps",
    "architecture_constraints",
    "security_constraints",
    "verification_obligations",
)
RETRIEVERS_USED = ("explicit", "authority", "lexical", "structural")


class ContextService:
    """Async, PostgreSQL-backed writer for `context_packages` (Chapter
    3.8). Each public method opens and commits its own unit of work
    unless one is supplied, so a caller composing a cross-module
    transaction (Chapter 3.5) can share it instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        events: EventService | None = None,
        repository: ContextRepository | None = None,
        clock: Clock | None = None,
        root: Path | None = None,
        context_budget_tokens: int = DEFAULT_CONTEXT_BUDGET_TOKENS,
    ) -> None:
        self._engine = engine
        self._events = events or EventService(engine)
        self._repository = repository or ContextRepository()
        self._clock = clock or SystemClock()
        self._root = root or repo_root()
        self._context_budget_tokens = context_budget_tokens

    async def _run(
        self,
        uow: PostgresUnitOfWork | None,
        tenant_id: UUID,
        project_id: UUID,
        body: Callable[[PostgresUnitOfWork], Awaitable[T]],
    ) -> T:
        if uow is not None:
            return await body(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as owned:
            result = await body(owned)
            await owned.commit()
            return result

    async def compile(
        self,
        *,
        task: Task,
        context_budget_tokens: int | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> ContextPackage | ContextBudgetExceeded:
        """Compile and persist a new `ContextPackage` version for `task`.

        Takes an already-materialised `Task` rather than a bare `task_id`:
        `engine.missions.repository.MissionsRepository` has no
        get-by-`task_id` read method today, and this mission's brief
        forbids adding new methods to `engine.missions` beyond calling
        its existing public surface. The caller (whoever resolves a Task
        for compilation — a future execution/scheduling module) is
        expected to have already read the `Task` row through
        `engine.missions`' existing methods."""
        tenant_id = task.tenant_id
        project_id = task.project_id
        mission_id = task.mission_id
        budget = (
            context_budget_tokens
            if context_budget_tokens is not None
            else self._context_budget_tokens
        )

        async def _op(
            active: PostgresUnitOfWork,
        ) -> ContextPackage | ContextBudgetExceeded:
            expected_write_scope = tuple(task.expected_write_scope)
            discovery = discover(task, root=self._root)

            explicit_items = explicit.retrieve(
                discovery, root=self._root, expected_write_scope=expected_write_scope
            )
            authority_result = await authority.retrieve(
                active.connection,
                project_id=project_id,
                requirement_refs=discovery.requirement_refs,
            )
            lexical_items = lexical.retrieve(
                task, root=self._root, expected_write_scope=expected_write_scope
            )
            structural_items = structural.retrieve(
                task,
                discovery,
                root=self._root,
                expected_write_scope=expected_write_scope,
            )
            retriever_results: dict[str, list[ContextItem]] = {
                "explicit": explicit_items,
                "authority": authority_result.items,
                "lexical": lexical_items,
                "structural": structural_items,
            }
            fused = fuse(retriever_results)

            assembled = assemble(task, fused, budget_tokens=budget)
            if isinstance(assembled, ContextBudgetExceeded):
                return assembled

            coverage = compute_coverage(
                task, discovery, authority_result, fused, assembled
            )
            coverage_json = coverage.to_json()
            status = (
                "INCOMPLETE"
                if any(
                    coverage.required_statuses()[category] == "missing"
                    for category in REQUIRED_COVERAGE_CATEGORIES
                )
                else "COMPLETE"
            )
            index_version = current_commit_sha(self._root)
            digest = assembly_hash(
                task_id=task.task_id,
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                index_version=index_version,
                index_lag_commits=0,
                coverage=coverage_json,
                included_items=assembled.included,
            )
            version = await self._repository.next_version(
                active.connection, task.task_id
            )
            now = self._clock.now()
            package = ContextPackage(
                package_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                task_id=task.task_id,
                version=version,
                assembly_hash=digest,
                index_version=index_version,
                index_lag_commits=0,
                coverage=coverage_json,
                status=status,
                retrievers_used=list(RETRIEVERS_USED),
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_context_package(active.connection, package)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="ContextPackageCompiled",
                aggregate_type="context_package",
                aggregate_id=package.package_id,
                mission_id=mission_id,
                task_id=task.task_id,
                payload={
                    "version": version,
                    "status": status,
                    "assembly_hash": digest,
                },
                uow=active,
            )
            return package

        return await self._run(uow, tenant_id, project_id, _op)
