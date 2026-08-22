"""Production Context Intelligence — the sole writer of `context_packages`
rows in PostgreSQL (Chapter 2.6, 3.5, 3.8, 5.1).

`ContextService.compile()` runs the Stage 1 slice of the Chapter 5.1
pipeline end to end: Discovery -> the four Stage 1 retrievers (explicit,
authority, lexical, structural; Chapter 5.2) -> reciprocal rank fusion
with authority-rank weighting (Chapter 5.3) -> budget-aware assembly with
Chapter 5.7's eviction priority order -> the Chapter 5.8 coverage
contract -> a versioned, hashed `ContextPackage` row (Chapter 3.10).

The semantic retriever and its Chapter 5.4 index lifecycle are wired
here, but gated behind `semantic_retrieval_enabled` (default `False`):
Chapter 5.2 requires semantic retrieval to "demonstrate uplift on the
eval corpus against a lexical+structural baseline before it is enabled
by default" (Stage 3, Chapter 5.13). No eval corpus/promotion gate
exists yet (EDR-0002, `docs/truth/edr/EDR-0002-semantic-retriever-
default-gating.md`), so `compile()` never consults the index or the
semantic retriever unless a caller explicitly opts in. When opted in,
`compile()` consults the active semantic index, runs the semantic
retriever when one exists, and applies the Chapter 5.4 staleness gate
(`block` past `DEFAULT_INDEX_LAG_BLOCK_COMMITS`, `warn` past
`DEFAULT_INDEX_LAG_WARN_COMMITS`). See `engine.context.index_service`
and `engine.context.retrievers.semantic`.

Conflict adjudication (Chapter 5.6, `engine.context.conflict`) and the
Context Critic (Chapter 5.9, `engine.context.critic`) are wired in after
assembly and coverage: `detect_conflicts()` runs over the authority
retriever's resolved Requirements/EDRs and, if it finds a rank<=6
contradiction, forces `status="CONFLICTED"` and persists one
`ContextConflict` row per contradiction (Chapter 5.6: "the DCE must not
merge or silently prefer one... Autonomous execution... is blocked until
resolved"). Absent a conflict, `evaluate_trigger()` checks Chapter 5.9's
five conditions and, if any hold, `run_critic()` either recovers already-
fused-but-evicted evidence for a `partial` category (persisted as a
`requested_additional_retrieval` `ContextCriticFinding`, and folded back
into this same package's assembled set / coverage) or raises a
`raised_finding` `ContextCriticFinding` when it cannot. See
`engine.context.critic` for exactly which of the five conditions are
computed from real signals versus explicitly parameterised because no
real data source exists yet (Chapter 5.11 failure attribution).

Deliberately out of scope, per the mission brief: dependency/graph/
temporal/documentation/visual retrievers, just-in-time expansion (needs
worker runs, Chapter 5.12/DDE-011+), and the knowledge-graph derived/
asserted split (Chapter 5.10/DDE-033). Chapter 5.6's "raise an EDR/
decision task (`blocks_on_decision` edge in the graph)" resolution path
is not wired here: `engine.missions.kernel` only recognises `depends_on`/
`produces_contract_for` edges today (no `blocks_on_decision` edge type
exists to raise), so a conflict's only real, honest effect this mission
delivers is the blocking `CONFLICTED` status plus the durable
`ContextConflict` record a human or a future mission resolves against.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.context.assembly import DEFAULT_CONTEXT_BUDGET_TOKENS, assemble
from engine.context.conflict import detect_conflicts
from engine.context.coverage import compute_coverage
from engine.context.critic import (
    DEFAULT_CRITIC_CONFIDENCE_THRESHOLD,
    evaluate_trigger,
    run_critic,
)
from engine.context.discovery import discover
from engine.context.fusion import fuse
from engine.context.hashing import assembly_hash
from engine.context.index_service import (
    DEFAULT_INDEX_LAG_BLOCK_COMMITS,
    DEFAULT_INDEX_LAG_WARN_COMMITS,
    ContextIndexService,
    staleness_action,
)
from engine.context.model import (
    AUTHORITY_RANK_EDR,
    AUTHORITY_RANK_REQUIREMENT,
    ContextBudgetExceeded,
    ContextItem,
)
from engine.context.repo import current_commit_sha, repo_root
from engine.context.repository import (
    ContextConflictRepository,
    ContextCriticFindingRepository,
    ContextRepository,
)
from engine.context.retrievers import authority, explicit, lexical, semantic, structural
from engine.contracts.context_conflict import ContextConflict
from engine.contracts.context_critic_finding import ContextCriticFinding
from engine.contracts.context_package import ContextPackage
from engine.contracts.task import Task
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
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
        index_service: ContextIndexService | None = None,
        index_lag_warn_commits: int = DEFAULT_INDEX_LAG_WARN_COMMITS,
        index_lag_block_commits: int = DEFAULT_INDEX_LAG_BLOCK_COMMITS,
        semantic_retrieval_enabled: bool = False,
        conflict_repository: ContextConflictRepository | None = None,
        critic_finding_repository: ContextCriticFindingRepository | None = None,
        critic_confidence_threshold: float = DEFAULT_CRITIC_CONFIDENCE_THRESHOLD,
    ) -> None:
        self._engine = engine
        self._events = events or EventService(engine)
        self._repository = repository or ContextRepository()
        self._clock = clock or SystemClock()
        self._root = root or repo_root()
        self._context_budget_tokens = context_budget_tokens
        self._index_service = index_service or ContextIndexService(
            engine, root=self._root
        )
        self._index_lag_warn_commits = index_lag_warn_commits
        self._index_lag_block_commits = index_lag_block_commits
        self._semantic_retrieval_enabled = semantic_retrieval_enabled
        self._conflict_repository = conflict_repository or ContextConflictRepository()
        self._critic_finding_repository = (
            critic_finding_repository or ContextCriticFindingRepository()
        )
        self._critic_confidence_threshold = critic_confidence_threshold

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
        previously_context_attributed_failure: bool = False,
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
        `engine.missions`' existing methods.

        `previously_context_attributed_failure` feeds Chapter 5.9's fifth
        Context Critic trigger condition ("the task is a repair of a
        previously context-attributed failure"). Chapter 5.11's
        failure-attribution pipeline (`engine.attribution`, DDE-034) is
        real today, but no production caller of `compile()` resolves a
        `Task`'s prior `FailureAttribution` history yet, so this
        parameter defaults to `False`. A caller that does not hold
        genuine Chapter 5.11 attribution data must never pass `True` here
        (see `engine.context.critic` for the full explanation)."""
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
            index_state = (
                await self._index_service.load_state(
                    tenant_id=tenant_id, project_id=project_id, uow=active
                )
                if self._semantic_retrieval_enabled
                else None
            )
            semantic_items: list[ContextItem] = []
            if index_state is not None:
                semantic_items = await semantic.retrieve(
                    active.connection,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    index_version=index_state.index.current_version,
                    task=task,
                    expected_write_scope=expected_write_scope,
                )
            retriever_results: dict[str, list[ContextItem]] = {
                "explicit": explicit_items,
                "authority": authority_result.items,
                "lexical": lexical_items,
                "structural": structural_items,
            }
            if index_state is not None:
                retriever_results["semantic"] = semantic_items
            fused = fuse(retriever_results)

            assembled = assemble(task, fused, budget_tokens=budget)
            if isinstance(assembled, ContextBudgetExceeded):
                return assembled

            coverage = compute_coverage(
                task, discovery, authority_result, fused, assembled
            )

            detected_conflicts = detect_conflicts(
                authority_result,
                requirement_authority_rank=AUTHORITY_RANK_REQUIREMENT,
                edr_authority_rank=AUTHORITY_RANK_EDR,
            )

            critic_trigger = None
            critic_outcome = None
            if not detected_conflicts:
                critic_trigger = evaluate_trigger(
                    task=task,
                    coverage=coverage,
                    assembled=assembled,
                    confidence_threshold=self._critic_confidence_threshold,
                    previously_context_attributed_failure=(
                        previously_context_attributed_failure
                    ),
                )
                if critic_trigger.triggered:
                    critic_outcome = run_critic(
                        coverage=coverage, assembled=assembled, budget_tokens=budget
                    )
                    if critic_outcome.reassembled is not None:
                        assembled = critic_outcome.reassembled
                        coverage = compute_coverage(
                            task, discovery, authority_result, fused, assembled
                        )

            coverage_json = coverage.to_json()
            if critic_outcome is not None and critic_outcome.action == "raised_finding":
                cast(list[str], coverage_json["known_unresolved_questions"]).append(
                    "Context Critic triggered ("
                    + ", ".join(critic_trigger.reasons if critic_trigger else ())
                    + ") and could not resolve the gap from already-retrieved "
                    "evidence; escalated as a Context Finding for human/other-"
                    "system review (Chapter 5.9)."
                )

            if detected_conflicts:
                status = "CONFLICTED"
            else:
                status = (
                    "INCOMPLETE"
                    if any(
                        coverage.required_statuses()[category] == "missing"
                        for category in REQUIRED_COVERAGE_CATEGORIES
                    )
                    else "COMPLETE"
                )
            if index_state is None:
                index_version = current_commit_sha(self._root)
                index_lag_commits = 0
            else:
                index_version = index_state.index.current_version
                index_lag_commits = index_state.lag_commits
                action = staleness_action(
                    index_lag_commits,
                    warn_threshold=self._index_lag_warn_commits,
                    block_threshold=self._index_lag_block_commits,
                )
                if action == "block":
                    raise DdeError(
                        "CONTEXT_STALE",
                        "Semantic index is too far behind the workspace base "
                        "revision; autonomous execution blocked",
                        details={
                            "index_version": index_version,
                            "index_lag_commits": index_lag_commits,
                            "block_threshold": self._index_lag_block_commits,
                        },
                    )
                if action == "warn":
                    cast(list[str], coverage_json["known_unresolved_questions"]).append(
                        f"Semantic index is {index_lag_commits} commits behind "
                        "the workspace base revision"
                    )
            digest = assembly_hash(
                task_id=task.task_id,
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                index_version=index_version,
                index_lag_commits=index_lag_commits,
                coverage=coverage_json,
                included_items=assembled.included,
            )
            version = await self._repository.next_version(
                active.connection, task.task_id
            )
            now = self._clock.now()
            retrievers_used = list(RETRIEVERS_USED)
            if index_state is not None:
                retrievers_used.append("semantic")
            package_id = uuid7()
            package = ContextPackage(
                package_id=package_id,
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                task_id=task.task_id,
                version=version,
                assembly_hash=digest,
                index_version=index_version,
                index_lag_commits=index_lag_commits,
                coverage=coverage_json,
                status=status,
                retrievers_used=retrievers_used,
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

            for detected in detected_conflicts:
                conflict = ContextConflict(
                    conflict_id=uuid7(),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission_id=mission_id,
                    task_id=task.task_id,
                    package_id=package_id,
                    item_a_key=detected.item_a_key,
                    item_a_authority_rank=detected.item_a_authority_rank,
                    item_b_key=detected.item_b_key,
                    item_b_authority_rank=detected.item_b_authority_rank,
                    contradiction_type=detected.contradiction_type,
                    affected_success_criteria=list(detected.affected_success_criteria),
                    status="open",
                    resolution_method=None,
                    resolved_at=None,
                    created_at=now,
                    updated_at=now,
                )
                await self._conflict_repository.insert_conflict(
                    active.connection, conflict
                )
            if detected_conflicts:
                await self._events.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    event_type="ContextConflictDetected",
                    aggregate_type="context_package",
                    aggregate_id=package_id,
                    mission_id=mission_id,
                    task_id=task.task_id,
                    payload={
                        "conflict_count": len(detected_conflicts),
                        "contradiction_types": sorted(
                            {c.contradiction_type for c in detected_conflicts}
                        ),
                    },
                    uow=active,
                )

            if critic_outcome is not None and critic_trigger is not None:
                finding = ContextCriticFinding(
                    finding_id=uuid7(),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission_id=mission_id,
                    task_id=task.task_id,
                    package_id=package_id,
                    trigger_reasons=list(critic_trigger.reasons),
                    confidence=critic_trigger.confidence,
                    action=critic_outcome.action,
                    outcome_summary=critic_outcome.outcome_summary,
                    requires_human_review=(critic_outcome.action == "raised_finding"),
                    reviewed=False,
                    reviewed_at=None,
                    cost_tokens_estimate=critic_outcome.cost_tokens_estimate,
                    created_at=now,
                    updated_at=now,
                )
                await self._critic_finding_repository.insert_finding(
                    active.connection, finding
                )
                await self._events.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    event_type="ContextCriticTriggered",
                    aggregate_type="context_package",
                    aggregate_id=package_id,
                    mission_id=mission_id,
                    task_id=task.task_id,
                    payload={
                        "action": critic_outcome.action,
                        "trigger_reasons": list(critic_trigger.reasons),
                        "cost_tokens_estimate": critic_outcome.cost_tokens_estimate,
                    },
                    uow=active,
                )
            return package

        return await self._run(uow, tenant_id, project_id, _op)
