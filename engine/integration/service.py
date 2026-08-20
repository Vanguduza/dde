"""Production Integration Manager -- the sole writer of `write_scope_leases`/
`integration_proposals` rows in PostgreSQL (Chapter 3.5, 3.8, 10).

`WriteScopeLeaseService` implements Chapter 10.3: reserving a lease over a
task's declared write scope and refusing a genuinely overlapping exclusive
scope within the same project, computed with the same normalised-prefix
comparison `engine.planning.validate` already uses for the identical rule at
scheduling time (`engine.integration.scope`).

`IntegrationQueueService` implements Chapter 10.4's merge queue exactly:
a project-scoped PostgreSQL advisory lock serialises one proposal at a time;
a real `git rebase` inside the task's own workspace worktree detects a real
textual conflict (never resolved here -- Chapter 10.5: "Never resolved by
the queue itself"); a real scope check catches a diff that reaches outside
its `WriteScopeLease`; a real, already-`PASSED` `VerificationRun` (Chapter
11, DDE-012) gates the fast-forward onto the mission integration branch
(Chapter 10.2). Composes `engine.workspaces.service.WorkspaceService` (for
the workspace's real worktree path) and reads `engine.verification`'s
`VerificationRunRepository` directly, exactly as `engine.workers.service.
WorkerManagerService` composes sibling services under one shared unit of
work (Chapter 3.5).

**Flagged Stage 1 simplification.** Chapter 10.4 step 5 describes running
full post-integration verification ("build, unit, contract, affected
integration tests, domain invariants, and the mission's AcceptanceOracle
subset") against the merge candidate. This queue still wires that gate to
an already-`PASSED` `VerificationRun` produced pre-integration (DDE-012)
-- re-running verification against the rebased candidate needs a second,
post-integration verification pass Stage 1 did not build.

**DDE-021.** Chapter 9.7's mandatory diff gates now run at Chapter 10.4
step 3, inside `VALIDATING`, after the WriteScopeLease scope check and
before the merge candidate is verified. See
`engine.integration.gate_service.DiffGateService` for the evaluator, the
scanner-honesty notes, and the exact deferrals (Gitleaks/Semgrep/Syft/
Grype CLIs, live OSV, donor taint, DDE-026 approvals).

Deliberately out of Stage 1 scope, per the mission brief: emitting a real
`repair` task on `CONFLICT(textual)`/`CONFLICT(semantic)` (needs the Task
Planner's replan machinery, Chapter 4.6, not wired to this module),
escalating to replanning after repeated conflicts (Chapter 10.5's "default
> 2" rule -- `attempts` is tracked and returned but nothing acts on it),
releasing a mission's write-scope leases on mainline advancement (Chapter
10.8 -- that is `main`-level, mission-completion behaviour; this queue only
fast-forwards the *mission* integration branch), and incremental reindex
triggering (Chapter 5.4, needs `engine.context` capability this mission does
not build).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.context.repo import repo_root
from engine.contracts.integration_proposal import IntegrationProposal
from engine.contracts.workspace import Workspace
from engine.contracts.write_scope_lease import WriteScopeLease
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.core.state_machine import transition
from engine.events.service import EventService
from engine.integration import git
from engine.integration.gate_service import DiffGateService
from engine.integration.repository import (
    IntegrationProposalRepository,
    WriteScopeLeaseRepository,
)
from engine.integration.scope import leases_overlap, path_in_scope
from engine.integration.states import (
    INTEGRATION_PROPOSAL_TRANSITIONS,
    WRITE_SCOPE_LEASE_TRANSITIONS,
)
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work
from engine.verification.repository import VerificationRunRepository

T = TypeVar("T")

#: Chapter 10.3 names no concrete TTL; a scope lease's real expiry is "with
#: the task attempt" (event-driven, via `release()`), not a fixed wall-clock
#: window. This constant is only the stored `expires_at` default a caller
#: can rely on for observability -- Stage 1 has no sweeper that acts on it.
DEFAULT_LEASE_TTL = timedelta(hours=24)

HELD_LEASE_STATUSES: frozenset[str] = frozenset({"RESERVED", "ACTIVE"})


class WriteScopeLeaseService:
    """Async, PostgreSQL-backed writer for `write_scope_leases` (Chapter
    3.8: "Status only" mutable). Each public method opens and commits its
    own unit of work unless one is supplied, so a caller composing a
    cross-module transaction (Chapter 3.5) can share it instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        events: EventService | None = None,
        repository: WriteScopeLeaseRepository | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._events = events or EventService(engine)
        self._repository = repository or WriteScopeLeaseRepository()
        self._clock = clock or SystemClock()

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

    async def acquire(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        task_id: UUID,
        scope_patterns: list[str],
        exclusive: bool = True,
        ttl: timedelta = DEFAULT_LEASE_TTL,
        uow: PostgresUnitOfWork | None = None,
    ) -> WriteScopeLease:
        """Chapter 10.3: "The Task Planner reserves write scopes before
        scheduling." Idempotent for the same `task_id`/`scope_patterns`
        pair -- a caller that re-plans the same task without releasing its
        prior lease gets that lease back rather than a spurious self
        conflict. Raises `WRITE_SCOPE_CONFLICT` for a genuine overlap with
        another task's still-held exclusive scope in the same project."""

        async def _op(active: PostgresUnitOfWork) -> WriteScopeLease:
            own = await self._repository.list_held_for_task(active.connection, task_id)
            for existing in own:
                if (
                    existing.scope_patterns == list(scope_patterns)
                    and existing.exclusive == exclusive
                ):
                    return existing
            if exclusive:
                held = await self._repository.list_held_for_project(
                    active.connection, project_id
                )
                for other in held:
                    if other.task_id == task_id or not other.exclusive:
                        continue
                    if leases_overlap(scope_patterns, other.scope_patterns):
                        raise DdeError(
                            "WRITE_SCOPE_CONFLICT",
                            "Requested write scope overlaps a lease another "
                            "task already holds in this project",
                            details={
                                "task_id": str(task_id),
                                "conflicting_task_id": str(other.task_id),
                                "conflicting_lease_id": str(other.lease_id),
                                "scope_patterns": list(scope_patterns),
                                "held_scope_patterns": list(other.scope_patterns),
                            },
                        )
            now = self._clock.now()
            lease = WriteScopeLease(
                lease_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                task_id=task_id,
                scope_patterns=list(scope_patterns),
                exclusive=exclusive,
                status="RESERVED",
                acquired_at=now,
                expires_at=now + ttl,
                released_at=None,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_lease(active.connection, lease)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="WriteScopeLeaseReserved",
                aggregate_type="write_scope_lease",
                aggregate_id=lease.lease_id,
                mission_id=mission_id,
                task_id=task_id,
                payload={
                    "scope_patterns": list(scope_patterns),
                    "exclusive": exclusive,
                },
                uow=active,
            )
            return lease

        return await self._run(uow, tenant_id, project_id, _op)

    async def activate(
        self, *, lease: WriteScopeLease, uow: PostgresUnitOfWork | None = None
    ) -> WriteScopeLease:
        return await self._transition(lease, "ACTIVE", uow=uow)

    async def release(
        self,
        *,
        lease: WriteScopeLease,
        target_status: str = "RELEASED",
        uow: PostgresUnitOfWork | None = None,
    ) -> WriteScopeLease:
        """Chapter 10.3: "released on RETIRE/SUPERSEDE only after the
        workspace is destroyed" -- `target_status` lets a caller record
        either `RELEASED` (normal completion) or `EXPIRED`."""
        return await self._transition(lease, target_status, uow=uow)

    async def _transition(
        self,
        lease: WriteScopeLease,
        target_status: str,
        *,
        uow: PostgresUnitOfWork | None,
    ) -> WriteScopeLease:
        async def _op(active: PostgresUnitOfWork) -> WriteScopeLease:
            current = await self._require_lease(active, lease.lease_id)
            next_status = transition(
                current.status, target_status, WRITE_SCOPE_LEASE_TRANSITIONS
            )
            now = self._clock.now()
            fields: dict[str, object] = {"status": next_status, "updated_at": now}
            if next_status in {"RELEASED", "EXPIRED"}:
                fields["released_at"] = now
            rowcount = await self._repository.update_lease(
                active.connection, current.lease_id, fields=fields
            )
            if rowcount != 1:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Unknown write scope lease",
                    details={"lease_id": str(current.lease_id)},
                )
            updated = await self._require_lease(active, current.lease_id)
            await self._events.append(
                tenant_id=updated.tenant_id,
                project_id=updated.project_id,
                event_type="WriteScopeLeaseTransitioned",
                aggregate_type="write_scope_lease",
                aggregate_id=updated.lease_id,
                mission_id=updated.mission_id,
                task_id=updated.task_id,
                payload={"from": current.status, "to": updated.status},
                uow=active,
            )
            return updated

        return await self._run(uow, lease.tenant_id, lease.project_id, _op)

    async def get_lease(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        lease_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> WriteScopeLease:
        async def _op(active: PostgresUnitOfWork) -> WriteScopeLease:
            return await self._require_lease(active, lease_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def _require_lease(
        self, active: PostgresUnitOfWork, lease_id: UUID
    ) -> WriteScopeLease:
        record = await self._repository.get_lease(active.connection, lease_id)
        if record is None:
            raise DdeError("POLICY_DENIED", "Unknown write scope lease")
        return record


class IntegrationQueueService:
    """Async, PostgreSQL-backed writer for `integration_proposals` (Chapter
    3.8). Each public method opens and commits its own unit of work unless
    one is supplied, so a caller composing a cross-module transaction
    (Chapter 3.5) can share it instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        events: EventService | None = None,
        proposal_repository: IntegrationProposalRepository | None = None,
        lease_repository: WriteScopeLeaseRepository | None = None,
        verification_run_repository: VerificationRunRepository | None = None,
        gates: DiffGateService | None = None,
        clock: Clock | None = None,
        root: Path | None = None,
    ) -> None:
        self._engine = engine
        self._events = events or EventService(engine)
        self._proposals = proposal_repository or IntegrationProposalRepository()
        self._leases = lease_repository or WriteScopeLeaseRepository()
        self._verification_runs = (
            verification_run_repository or VerificationRunRepository()
        )
        self._gates = gates or DiffGateService(engine, events=self._events)
        self._clock = clock or SystemClock()
        self._root = root or repo_root()

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

    def mission_branch_name(self, mission_id: UUID) -> str:
        """Chapter 10.2: `mission/<mission-id>`, one per mission."""
        return f"mission/{mission_id}"

    def task_branch_name(self, task_id: UUID, attempt_label: str) -> str:
        """Chapter 10.2: `task/<task-id>-a`, one per task attempt."""
        return f"task/{task_id}-{attempt_label}"

    async def ensure_mission_branch(
        self, *, mission_id: UUID, base_revision: str
    ) -> str:
        """Bootstraps `mission/<mission_id>` at `base_revision` the first
        time any proposal for this mission reaches the queue; returns the
        branch's real, current head either way."""
        branch = self.mission_branch_name(mission_id)
        if not git.branch_exists(self._root, branch):
            git.create_branch(self._root, branch, base_revision)
        return git.rev_parse(self._root, branch)

    async def submit(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        task_id: UUID,
        task_attempt_id: UUID,
        workspace: Workspace,
        lease: WriteScopeLease,
        verification_run_id: UUID,
        attempt_label: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> IntegrationProposal:
        """Chapter 3.9 step 16: "Integration proposal enters the merge
        queue." Turns the workspace's real, still-uncommitted diff into a
        real commit (Chapter 10.1: integration, never the worker, owns
        that), stands up its real `task/<task-id>-<label>` branch, and
        queues a real proposal referencing the real `WriteScopeLease` and
        `VerificationRun` it depends on."""
        if lease.task_id != task_id:
            raise DdeError(
                "POLICY_DENIED",
                "WriteScopeLease does not belong to this task",
                details={"task_id": str(task_id), "lease_task_id": str(lease.task_id)},
            )
        if lease.status not in HELD_LEASE_STATUSES:
            raise DdeError(
                "POLICY_DENIED",
                f"WriteScopeLease is {lease.status}, not held",
                details={"lease_id": str(lease.lease_id)},
            )
        if workspace.workspace_path is None:
            raise DdeError(
                "ENVIRONMENT_FAILED",
                "Workspace has no filesystem path to commit from",
                details={"workspace_id": str(workspace.workspace_id)},
            )
        worktree_path = Path(workspace.workspace_path)
        base_revision = workspace.base_revision or git.rev_parse(self._root, "HEAD")
        branch = self.task_branch_name(task_id, attempt_label)
        proposed_revision = git.commit_all(
            worktree_path,
            f"Integrate task {task_id} attempt {attempt_label}",
        )
        if git.branch_exists(self._root, branch):
            git.update_ref(self._root, branch, proposed_revision)
        else:
            git.create_branch(self._root, branch, proposed_revision)
        changed_paths = git.diff_name_only(self._root, base_revision, proposed_revision)
        diff_summary = f"{len(changed_paths)} file(s) changed"

        async def _op(active: PostgresUnitOfWork) -> IntegrationProposal:
            prior = await self._proposals.list_for_task(active.connection, task_id)
            now = self._clock.now()
            proposal = IntegrationProposal(
                proposal_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                task_id=task_id,
                task_attempt_id=task_attempt_id,
                source_branch=branch,
                base_revision=base_revision,
                proposed_revision=proposed_revision,
                diff_summary=diff_summary,
                changed_paths=changed_paths,
                scope_lease_id=lease.lease_id,
                pre_integration_verification_ref=verification_run_id,
                status="QUEUED",
                conflict_class=None,
                attempts=len(prior) + 1,
                created_at=now,
                updated_at=now,
            )
            await self._proposals.insert_proposal(active.connection, proposal)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="IntegrationProposalQueued",
                aggregate_type="integration_proposal",
                aggregate_id=proposal.proposal_id,
                mission_id=mission_id,
                task_id=task_id,
                payload={
                    "source_branch": branch,
                    "base_revision": base_revision,
                    "proposed_revision": proposed_revision,
                    "changed_paths": changed_paths,
                },
                uow=active,
            )
            return proposal

        return await self._run(uow, tenant_id, project_id, _op)

    async def integrate(
        self,
        *,
        proposal: IntegrationProposal,
        workspace: Workspace,
        uow: PostgresUnitOfWork | None = None,
    ) -> IntegrationProposal:
        """Chapter 10.4's queue algorithm, steps 1-8, minus the deferrals
        the module docstring names. Idempotent against a proposal already
        past `QUEUED`: a repeated call simply returns its current
        (terminal) state rather than re-running the algorithm."""
        if workspace.workspace_path is None:
            raise DdeError(
                "ENVIRONMENT_FAILED",
                "Workspace has no filesystem path to rebase in",
                details={"workspace_id": str(workspace.workspace_id)},
            )
        worktree_path = Path(workspace.workspace_path)

        async def _op(active: PostgresUnitOfWork) -> IntegrationProposal:
            await self._acquire_project_lock(active, proposal.project_id)
            current = await self._require_proposal(active, proposal.proposal_id)
            if current.status != "QUEUED":
                return current

            mission_head = await self.ensure_mission_branch(
                mission_id=current.mission_id, base_revision=current.base_revision
            )
            target_revision: str | None = current.proposed_revision
            if current.base_revision != mission_head:
                current = await self._transition(active, current, "REBASING")
                rebase = git.rebase_onto(worktree_path, mission_head)
                if not rebase.ok:
                    return await self._terminal(
                        active,
                        current,
                        "CONFLICT",
                        conflict_class="textual",
                        detail=rebase.stderr,
                        event_type="IntegrationConflict",
                    )
                target_revision = rebase.revision
                if target_revision is None:  # pragma: no cover - defensive
                    raise DdeError(
                        "MERGE_CONFLICT",
                        "Rebase reported success without a resulting revision",
                    )
                git.update_ref(self._root, current.source_branch, target_revision)
                current = await self._update_fields(
                    active,
                    current,
                    base_revision=mission_head,
                    proposed_revision=target_revision,
                )

            current = await self._transition(active, current, "VALIDATING")

            if target_revision is None:  # pragma: no cover - defensive
                raise DdeError(
                    "MERGE_CONFLICT",
                    "No resulting revision to validate after rebase",
                )
            lease = await self._require_lease(active, current.scope_lease_id)
            changed_paths = git.diff_name_only(
                self._root, mission_head, target_revision
            )
            out_of_scope = [
                path
                for path in changed_paths
                if not path_in_scope(path, lease.scope_patterns)
            ]
            current = await self._update_fields(
                active, current, changed_paths=changed_paths
            )
            if out_of_scope:
                return await self._terminal(
                    active,
                    current,
                    "REJECTED",
                    conflict_class="scope_violation",
                    detail=f"changed paths outside lease scope: {out_of_scope}",
                    event_type="IntegrationRejected",
                )

            gate_report = await self._gates.evaluate(
                proposal=current,
                repo_root=self._root,
                base_revision=mission_head,
                proposed_revision=target_revision,
                changed_paths=changed_paths,
                uow=active,
            )
            if gate_report.status != "PASSED":
                failed = [item.gate for item in gate_report.findings if not item.passed]
                return await self._terminal(
                    active,
                    current,
                    "REJECTED",
                    conflict_class="gate_failed",
                    detail=(
                        "mandatory diff gates failed: "
                        f"{failed}; quarantined={gate_report.quarantined}"
                    ),
                    event_type="IntegrationRejected",
                )

            candidate_ref = f"candidate/{current.proposal_id}"
            git.create_branch(self._root, candidate_ref, target_revision)
            try:
                current = await self._transition(active, current, "VERIFYING")
                verification_run = await self._verification_runs.get_run(
                    active.connection, current.pre_integration_verification_ref
                )
                if verification_run is None or verification_run.status != "PASSED":
                    return await self._terminal(
                        active,
                        current,
                        "REJECTED",
                        conflict_class=None,
                        detail="pre_integration_verification_ref is not a PASSED "
                        "VerificationRun",
                        event_type="IntegrationRejected",
                    )

                git.update_ref(
                    self._root,
                    self.mission_branch_name(current.mission_id),
                    target_revision,
                )
                merged = await self._transition(
                    active,
                    current,
                    "MERGED",
                    event_type="MergedToMission",
                    event_payload={
                        "mission_branch": self.mission_branch_name(current.mission_id),
                        "revision": target_revision,
                        "source_branch": current.source_branch,
                    },
                )
                return merged
            finally:
                git.delete_branch(self._root, candidate_ref)

        return await self._run(uow, proposal.tenant_id, proposal.project_id, _op)

    async def _acquire_project_lock(
        self, active: PostgresUnitOfWork, project_id: UUID
    ) -> None:
        """Chapter 3.5: "PostgreSQL advisory lock, key = project_id |
        Integration/merge queue | Serialise mainline advancement."
        Transaction-scoped: the lock releases automatically at commit or
        rollback, so no separate release call is needed."""
        await active.connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key)::bigint)"),
            {"key": str(project_id)},
        )

    async def _transition(
        self,
        active: PostgresUnitOfWork,
        current: IntegrationProposal,
        target_status: str,
        *,
        event_type: str | None = None,
        event_payload: dict[str, object] | None = None,
    ) -> IntegrationProposal:
        next_status = transition(
            current.status, target_status, INTEGRATION_PROPOSAL_TRANSITIONS
        )
        now = self._clock.now()
        rowcount = await self._proposals.update_proposal(
            active.connection,
            current.proposal_id,
            fields={"status": next_status, "updated_at": now},
        )
        if rowcount != 1:
            raise DdeError(
                "VERSION_CONFLICT",
                "Unknown integration proposal",
                details={"proposal_id": str(current.proposal_id)},
            )
        updated = await self._require_proposal(active, current.proposal_id)
        await self._events.append(
            tenant_id=updated.tenant_id,
            project_id=updated.project_id,
            event_type=event_type or "IntegrationProposalTransitioned",
            aggregate_type="integration_proposal",
            aggregate_id=updated.proposal_id,
            mission_id=updated.mission_id,
            task_id=updated.task_id,
            payload=event_payload or {"from": current.status, "to": updated.status},
            uow=active,
        )
        return updated

    async def _terminal(
        self,
        active: PostgresUnitOfWork,
        current: IntegrationProposal,
        target_status: str,
        *,
        conflict_class: str | None,
        detail: str,
        event_type: str,
    ) -> IntegrationProposal:
        next_status = transition(
            current.status, target_status, INTEGRATION_PROPOSAL_TRANSITIONS
        )
        now = self._clock.now()
        rowcount = await self._proposals.update_proposal(
            active.connection,
            current.proposal_id,
            fields={
                "status": next_status,
                "conflict_class": conflict_class,
                "updated_at": now,
            },
        )
        if rowcount != 1:
            raise DdeError(
                "VERSION_CONFLICT",
                "Unknown integration proposal",
                details={"proposal_id": str(current.proposal_id)},
            )
        updated = await self._require_proposal(active, current.proposal_id)
        await self._events.append(
            tenant_id=updated.tenant_id,
            project_id=updated.project_id,
            event_type=event_type,
            aggregate_type="integration_proposal",
            aggregate_id=updated.proposal_id,
            mission_id=updated.mission_id,
            task_id=updated.task_id,
            payload={"conflict_class": conflict_class, "detail": detail},
            uow=active,
        )
        return updated

    async def _update_fields(
        self,
        active: PostgresUnitOfWork,
        current: IntegrationProposal,
        **fields: object,
    ) -> IntegrationProposal:
        now = self._clock.now()
        rowcount = await self._proposals.update_proposal(
            active.connection,
            current.proposal_id,
            fields={**fields, "updated_at": now},
        )
        if rowcount != 1:
            raise DdeError(
                "VERSION_CONFLICT",
                "Unknown integration proposal",
                details={"proposal_id": str(current.proposal_id)},
            )
        return await self._require_proposal(active, current.proposal_id)

    async def get_proposal(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        proposal_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> IntegrationProposal:
        async def _op(active: PostgresUnitOfWork) -> IntegrationProposal:
            return await self._require_proposal(active, proposal_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def _require_proposal(
        self, active: PostgresUnitOfWork, proposal_id: UUID
    ) -> IntegrationProposal:
        record = await self._proposals.get_proposal(active.connection, proposal_id)
        if record is None:
            raise DdeError("POLICY_DENIED", "Unknown integration proposal")
        return record

    async def _require_lease(
        self, active: PostgresUnitOfWork, lease_id: UUID
    ) -> WriteScopeLease:
        record = await self._leases.get_lease(active.connection, lease_id)
        if record is None:
            raise DdeError("POLICY_DENIED", "Unknown write scope lease")
        return record
