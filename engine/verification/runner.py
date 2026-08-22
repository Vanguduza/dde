"""Verification runner (Chapter 11.1) -- the mechanical half of the chain:
given a completed `WorkerRun` and its `Workspace`, execute every check a
bound `AcceptanceOracle` declares, and hand the real, captured results to
the oracle's own evaluation (`engine.verification.oracle`) to produce a
real, persisted verdict.

Composes `engine.workspaces.service.WorkspaceService.execute()` (never
reimplements subprocess execution -- mission brief) under one shared
`PostgresUnitOfWork`, exactly as `engine.workers.service.WorkerManagerService`
composes `engine.missions.attempts.TaskAttemptService` and
`engine.environments.service.ExecutionEnvironmentService` (Chapter 3.5: a
transaction may span module boundaries).

Guarded end-to-end by `engine.events.idempotency.CommandLedger` on a
caller-supplied `idempotency_key`: a repeated invocation with the same key
never re-executes the checks -- it returns the first call's stored,
completed `VerificationRun` instead (AGENTS.md: "New async operation has a
durable identity, an idempotency key and observable state").

Chapter 11.4's generator/verifier independence holds by construction: this
runner never dispatches to a `WorkerAdapter`/worker profile at all -- every
check is a literal, DDE-declared command executed directly, so the worker
profile that produced the change under test never has a hand in judging it.
`Evidence.independence_flags` records that fact per evidence row rather than
merely asserting it in a docstring.

**Self-grading guardrails (research §4 item 1, SWE-bench issue #538).**
Before any oracle outcome executes, `run()` mechanically inspects the real
diff under verification (`engine.workspaces.git.diff_name_only` against the
workspace's base revision) with `engine.verification.guardrails.
assess_diff_independence`: undeclared edits to test-owned paths and added
files shadowing the oracle's expected-test layout are recorded on every
evidence row this run writes (`independence_flags["test_scope_findings"]`,
`test_scope_violation`). Disclosed scope: a violating diff still runs the
oracle's checks -- but a clean PASS over a harness-gaming diff is not
certified as independent: the run's status is forced to PARTIAL (never
PASSED), so Chapter 6.5 telemetry and downstream integration gates see an
untrusted verdict. Failing the run outright / raising SCOPE_VIOLATION into
the recovery matrix is deferred.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.attribution.service import FailureAttributionService
from engine.contracts.acceptance_oracle import AcceptanceOracle, ObservableOutcome
from engine.contracts.command_idempotency import CommandIdempotency
from engine.contracts.evidence import Evidence
from engine.contracts.task import Task
from engine.contracts.verification_run import (
    CheckResult,
    ObservableOutcomeResult,
    VerificationRun,
)
from engine.contracts.worker_run import WorkerRun
from engine.contracts.workspace import Workspace
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.hashing import canonical_json, sha256_hex
from engine.core.ids import uuid7
from engine.core.state_machine import transition
from engine.events.idempotency import CommandLedger
from engine.events.service import EventService
from engine.missions.attempts import TaskAttemptService
from engine.recovery.checkpoint_service import (
    CheckpointService,
    do_not_repeat_from_effects,
)
from engine.recovery.matrix import decide
from engine.telemetry.service import RoutingTelemetryService
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work
from engine.verification.checks import CheckSpec, run_check
from engine.verification.guardrails import (
    TestScopeAssessment,
    TestScopeFinding,
    assess_diff_independence,
    merge_flags,
)
from engine.verification.repository import (
    EvidenceRepository,
    VerificationRunRepository,
)
from engine.verification.states import VERIFICATION_RUN_TRANSITIONS
from engine.workers.repository import WorkerEventRepository
from engine.workspaces import git
from engine.workspaces.git import GitCommandError
from engine.workspaces.service import WorkspaceService

T = TypeVar("T")

#: Real, produced-by identity for every `Evidence` row this runner writes.
#: Never a worker profile -- Chapter 11.4's independence rule holds because
#: no worker profile is ever invoked here.
EVIDENCE_PRODUCED_BY = "capability:engine.verification.runner"
EVIDENCE_STATUS_RECORDED = "RECORDED"


def _run_request_hash(
    *,
    task_id: UUID,
    worker_run_id: UUID,
    oracle_id: UUID,
    oracle_version: str,
    workspace_id: UUID,
) -> str:
    return sha256_hex(
        canonical_json(
            {
                "task_id": str(task_id),
                "worker_run_id": str(worker_run_id),
                "oracle_id": str(oracle_id),
                "oracle_version": oracle_version,
                "workspace_id": str(workspace_id),
            }
        )
    )


def _outcome_check_spec(
    outcome: ObservableOutcome, *, is_negative_case: bool
) -> CheckSpec:
    binding = outcome.evidence_binding
    return CheckSpec(
        outcome_id=outcome.outcome_id,
        statement=outcome.statement,
        kind=binding.kind,
        ref=binding.ref,
        command=list(binding.command or []),
        is_negative_case=is_negative_case,
    )


def _outcome_status(check: CheckResult, *, is_negative_case: bool) -> str:
    if check.status == "ERRORED":
        return "ERRORED"
    held = check.status == "PASSED"
    if is_negative_case:
        return "FAILED" if held else "PASSED"
    return "PASSED" if held else "FAILED"


class VerificationRunnerService:
    """Async, PostgreSQL-backed writer for `verification_runs`/`evidence`
    (Chapter 3.8, both owned by `engine.verification`). Each public method
    opens and commits its own unit of work unless one is supplied, so a
    caller composing a cross-module transaction (Chapter 3.5) can share it
    instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        workspaces: WorkspaceService,
        events: EventService | None = None,
        commands: CommandLedger | None = None,
        run_repository: VerificationRunRepository | None = None,
        evidence_repository: EvidenceRepository | None = None,
        clock: Clock | None = None,
        attempts: TaskAttemptService | None = None,
        checkpoints: CheckpointService | None = None,
        worker_events: WorkerEventRepository | None = None,
        attribution: FailureAttributionService | None = None,
        telemetry: RoutingTelemetryService | None = None,
    ) -> None:
        self._engine = engine
        self._workspaces = workspaces
        self._events = events or EventService(engine)
        self._commands = commands or CommandLedger(engine)
        self._run_repository = run_repository or VerificationRunRepository()
        self._evidence_repository = evidence_repository or EvidenceRepository()
        self._clock = clock or SystemClock()
        self._attempts = attempts or TaskAttemptService(engine, events=self._events)
        self._checkpoints = checkpoints or CheckpointService(
            engine, events=self._events, clock=self._clock
        )
        self._worker_events = worker_events or WorkerEventRepository()
        self._attribution = attribution or FailureAttributionService(
            engine, events=self._events
        )
        self._telemetry = telemetry or RoutingTelemetryService(
            engine, events=self._events
        )

    async def _run_uow(
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

    async def run(
        self,
        *,
        task: Task,
        worker_run: WorkerRun,
        workspace: Workspace,
        oracle: AcceptanceOracle,
        idempotency_key: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> VerificationRun:
        """Chapter 3.9 step 14: "VerificationRun consumes durable outputs".
        Requires a `WorkerRun` already `COMPLETED` -- verification judges
        what a worker actually produced, it never races the worker."""
        if oracle.task_id != task.task_id:
            raise DdeError(
                "POLICY_DENIED",
                "AcceptanceOracle does not belong to this task",
                details={
                    "task_id": str(task.task_id),
                    "oracle_task_id": str(oracle.task_id),
                },
            )
        if worker_run.mission_id != task.mission_id:
            raise DdeError(
                "POLICY_DENIED",
                "WorkerRun does not belong to this task's mission",
                details={"mission_id": str(task.mission_id)},
            )
        if worker_run.status != "COMPLETED":
            raise DdeError(
                "POLICY_DENIED",
                f"WorkerRun is {worker_run.status}, not COMPLETED; nothing to verify",
                details={"run_id": str(worker_run.run_id)},
            )
        if worker_run.workspace_id != workspace.workspace_id:
            raise DdeError(
                "POLICY_DENIED",
                "Workspace does not match the WorkerRun's own workspace",
                details={
                    "worker_run_workspace_id": str(worker_run.workspace_id),
                    "workspace_id": str(workspace.workspace_id),
                },
            )

        tenant_id = task.tenant_id
        project_id = task.project_id
        request_hash = _run_request_hash(
            task_id=task.task_id,
            worker_run_id=worker_run.run_id,
            oracle_id=oracle.oracle_id,
            oracle_version=oracle.oracle_version,
            workspace_id=workspace.workspace_id,
        )

        async def _op(active: PostgresUnitOfWork) -> VerificationRun:
            record, is_new = await self._commands.begin(
                tenant_id=tenant_id,
                project_id=project_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                uow=active,
            )
            if not is_new:
                return self._replay_or_raise(record)

            sequence = await self._run_repository.next_sequence(
                active.connection, worker_run.run_id
            )
            now = self._clock.now()
            run = VerificationRun(
                verification_run_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=task.mission_id,
                task_id=task.task_id,
                task_attempt_id=worker_run.task_attempt_id,
                worker_run_id=worker_run.run_id,
                workspace_id=workspace.workspace_id,
                oracle_id=oracle.oracle_id,
                sequence=sequence,
                status="RUNNING",
                confidence=0.0,
                check_results=[],
                outcome_results=[],
                negative_case_results=[],
                evidence_refs=[],
                started_at=now,
                ended_at=None,
                created_at=now,
                updated_at=now,
            )
            await self._run_repository.insert_run(active.connection, run)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="VerificationRunStarted",
                aggregate_type="verification_run",
                aggregate_id=run.verification_run_id,
                mission_id=task.mission_id,
                task_id=task.task_id,
                payload={
                    "oracle_id": str(oracle.oracle_id),
                    "worker_run_id": str(worker_run.run_id),
                },
                uow=active,
            )

            check_results: list[CheckResult] = []
            outcome_results: list[ObservableOutcomeResult] = []
            negative_results: list[ObservableOutcomeResult] = []
            evidence_refs: list[UUID] = []
            integrated_revision = (
                workspace.current_revision or workspace.base_revision or "unknown"
            )

            # Self-grading guardrail (research §4 item 1): mechanically
            # inspect the diff under verification BEFORE any oracle
            # outcome runs, so a harness-gaming patch is recorded on every
            # evidence row this run produces.
            guardrail = await self._assess_guardrails(
                active,
                task=task,
                oracle=oracle,
                workspace=workspace,
            )

            for outcome in oracle.observable_outcomes:
                result, outcome_result, ev = await self._execute_outcome(
                    active,
                    task=task,
                    oracle=oracle,
                    run_id=run.verification_run_id,
                    outcome=outcome,
                    is_negative_case=False,
                    worker_run=worker_run,
                    workspace=workspace,
                    integrated_revision=integrated_revision,
                    guardrail=guardrail,
                )
                check_results.append(result)
                outcome_results.append(outcome_result)
                evidence_refs.append(ev.evidence_id)

            for outcome in oracle.negative_cases:
                result, outcome_result, ev = await self._execute_outcome(
                    active,
                    task=task,
                    oracle=oracle,
                    run_id=run.verification_run_id,
                    outcome=outcome,
                    is_negative_case=True,
                    worker_run=worker_run,
                    workspace=workspace,
                    integrated_revision=integrated_revision,
                    guardrail=guardrail,
                )
                check_results.append(result)
                negative_results.append(outcome_result)
                evidence_refs.append(ev.evidence_id)

            status, confidence = _evaluate(
                outcome_results=outcome_results,
                negative_results=negative_results,
                minimum_confidence=oracle.minimum_confidence,
                guardrail=guardrail,
            )
            ended_at = self._clock.now()
            next_status = transition(run.status, status, VERIFICATION_RUN_TRANSITIONS)
            fields: dict[str, object] = {
                "status": next_status,
                "confidence": confidence,
                "check_results": [
                    item.model_dump(mode="json") for item in check_results
                ],
                "outcome_results": [
                    item.model_dump(mode="json") for item in outcome_results
                ],
                "negative_case_results": [
                    item.model_dump(mode="json") for item in negative_results
                ],
                "evidence_refs": [str(item) for item in evidence_refs],
                "ended_at": ended_at,
                "updated_at": ended_at,
            }
            rowcount = await self._run_repository.update_run(
                active.connection, run.verification_run_id, fields=fields
            )
            if rowcount != 1:
                raise DdeError(
                    "POLICY_DENIED",
                    "Unknown verification run",
                    details={"verification_run_id": str(run.verification_run_id)},
                )
            finished = await self._require_run(active, run.verification_run_id)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type=f"VerificationRun{next_status.title()}",
                aggregate_type="verification_run",
                aggregate_id=finished.verification_run_id,
                mission_id=task.mission_id,
                task_id=task.task_id,
                payload={"status": next_status, "confidence": confidence},
                uow=active,
            )
            if next_status == "PASSED":
                await self._finalise_passed_attempt(
                    active,
                    task=task,
                    worker_run=worker_run,
                    workspace=workspace,
                    evidence_refs=evidence_refs,
                    verification_run_id=finished.verification_run_id,
                )
                prior = await self._run_repository.list_for_task(
                    active.connection, task.task_id
                )
                rework_count = sum(1 for row in prior if row.status == "FAILED")
                # Chapter 6.5: real telemetry recorded for every decision,
                # in the same transaction as the PASSED VerificationRun --
                # "must never be skipped" holds by construction.
                await self._telemetry.record_decision_outcome(
                    task=task,
                    worker_run=worker_run,
                    verification_run=finished,
                    rework_count=rework_count,
                    recovery_decision=None,
                    uow=active,
                )
            elif next_status == "FAILED":
                prior = await self._run_repository.list_for_task(
                    active.connection, task.task_id
                )
                count = sum(1 for row in prior if row.status == "FAILED")
                decision = decide("VERIFICATION_FAILURE", occurrence_count=count)
                await self._fail_unverified_attempt(
                    active,
                    task=task,
                    worker_run=worker_run,
                    workspace=workspace,
                    verification_run_id=finished.verification_run_id,
                )
                # Chapter 5.11: verification records whether this failure
                # was plausibly caused by context, in the same transaction
                # as the FAILED VerificationRun/TaskAttempt -- never a
                # detached, best-effort side query.
                attribution = await self._attribution.attribute_verification_failure(
                    task=task,
                    task_attempt_id=worker_run.task_attempt_id,
                    verification_run_id=finished.verification_run_id,
                    workspace=workspace,
                    uow=active,
                )
                # Chapter 6.5: real telemetry recorded for every decision,
                # in the same transaction as the FAILED VerificationRun --
                # closes the loop with Chapter 5.11's attribution above by
                # linking the same-transaction FailureAttribution row.
                await self._telemetry.record_decision_outcome(
                    task=task,
                    worker_run=worker_run,
                    verification_run=finished,
                    rework_count=count,
                    recovery_decision=decision,
                    failure_attribution_id=attribution.attribution_id,
                    uow=active,
                )
                await self._events.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    event_type="VerificationFailureRecovery",
                    aggregate_type="verification_run",
                    aggregate_id=finished.verification_run_id,
                    mission_id=task.mission_id,
                    task_id=task.task_id,
                    payload={
                        "action": decision.action,
                        "requires_replan": decision.requires_replan,
                        "allow_new_worker_run": decision.allow_new_worker_run,
                        "occurrence_count": count,
                    },
                    uow=active,
                )
            await self._commands.complete(
                tenant_id=tenant_id,
                project_id=project_id,
                command_id=record.command_id,
                result=finished.model_dump(mode="json"),
                uow=active,
            )
            return finished

        return await self._run_uow(uow, tenant_id, project_id, _op)

    async def _assess_guardrails(
        self,
        active: PostgresUnitOfWork,
        *,
        task: Task,
        oracle: AcceptanceOracle,
        workspace: Workspace,
    ) -> TestScopeAssessment:
        """Real diff under verification -> mechanical guardrail findings.

        The changed-file list is read from the workspace's own worktree via
        `engine.workspaces.git.diff_name_only` (committed and uncommitted
        changes against the base revision). This is deliberately a direct
        git *read* on DDE's own behalf inside the verification chain -- the
        same category as `create`/`cleanup`/`capture_revision`'s lifecycle
        git calls in `WorkspaceService` (which are ungated for exactly this
        reason: Chapter 3.9's order means no run-scoped lease exists to
        check, see that module's docstring). It is not a worker-requested
        capability operation and journals no external effect.
        """
        base = workspace.base_revision
        if not base or not workspace.workspace_path:
            # Without a usable base revision or worktree path there is
            # nothing to diff: no findings fabricated from absence.
            return TestScopeAssessment(findings=())
        try:
            changed_files = await asyncio.to_thread(
                git.diff_name_only,
                Path(workspace.workspace_path),
                base,
            )
        except (GitCommandError, OSError):
            # A workspace whose git state cannot be read must not yield a
            # clean bill of health by accident; surface an informational
            # finding instead of a violation we could not prove.
            return TestScopeAssessment(
                findings=(
                    TestScopeFinding(
                        kind="unreadable_diff",
                        path=str(workspace.workspace_id),
                        detail=(
                            "changed-file list could not be read from the "
                            "workspace; guardrail sweep ran on an empty diff"
                        ),
                        violation=False,
                    ),
                )
            )
        return assess_diff_independence(
            task=task, oracle=oracle, changed_files=changed_files
        )

    async def _finalise_passed_attempt(
        self,
        active: PostgresUnitOfWork,
        *,
        task: Task,
        worker_run: WorkerRun,
        workspace: Workspace,
        evidence_refs: list[UUID],
        verification_run_id: UUID,
    ) -> None:
        """Chapter 3.9 step 15: TaskAttempt finalised after verification."""
        effects = await self._workspaces.effects.list_for_run(
            tenant_id=task.tenant_id,
            project_id=task.project_id,
            worker_run_id=worker_run.run_id,
            uow=active,
        )
        worker_events = await self._worker_events.list_for_run(
            active.connection, worker_run.run_id
        )
        sequence = worker_events[-1].sequence if worker_events else 0
        checkpoint = await self._checkpoints.record(
            run=worker_run,
            task_id=task.task_id,
            workspace_revision=workspace.current_revision
            or workspace.base_revision
            or "",
            event_sequence=sequence,
            completed_work=[str(task.task_id)],
            verified_work=[str(task.task_id)],
            pending_work=[],
            known_failures=[],
            next_action="integrate",
            do_not_repeat=do_not_repeat_from_effects(effects),
            artifact_refs=[],
            lease_refs=[],
            idempotency_key=f"{verification_run_id}:attempt-finalise",
            uow=active,
        )
        await self._attempts.finalize(
            tenant_id=task.tenant_id,
            project_id=task.project_id,
            attempt_id=worker_run.task_attempt_id,
            verification_refs=evidence_refs,
            checkpoint_id=checkpoint.checkpoint_id,
            uow=active,
        )

    async def _fail_unverified_attempt(
        self,
        active: PostgresUnitOfWork,
        *,
        task: Task,
        worker_run: WorkerRun,
        workspace: Workspace,
        verification_run_id: UUID,
    ) -> None:
        """Chapter 12.3: VERIFICATION_FAILURE is a durable FAILED attempt,
        not an IN_PROGRESS row that a later invoke_run could treat as a
        first attempt. Failing evidence lives on the VerificationRun.
        """
        effects = await self._workspaces.effects.list_for_run(
            tenant_id=task.tenant_id,
            project_id=task.project_id,
            worker_run_id=worker_run.run_id,
            uow=active,
        )
        worker_events = await self._worker_events.list_for_run(
            active.connection, worker_run.run_id
        )
        sequence = worker_events[-1].sequence if worker_events else 0
        checkpoint = await self._checkpoints.record(
            run=worker_run,
            task_id=task.task_id,
            workspace_revision=workspace.current_revision
            or workspace.base_revision
            or "",
            event_sequence=sequence,
            completed_work=[str(task.task_id)],
            verified_work=[],
            pending_work=[str(task.task_id)],
            known_failures=["VERIFICATION_FAILURE"],
            next_action="repair",
            do_not_repeat=do_not_repeat_from_effects(effects),
            artifact_refs=[],
            lease_refs=[],
            idempotency_key=f"{verification_run_id}:attempt-fail",
            uow=active,
        )
        await self._attempts.fail(
            tenant_id=task.tenant_id,
            project_id=task.project_id,
            attempt_id=worker_run.task_attempt_id,
            failure_class="VERIFICATION_FAILURE",
            checkpoint_id=checkpoint.checkpoint_id,
            uow=active,
        )

    async def _execute_outcome(
        self,
        active: PostgresUnitOfWork,
        *,
        task: Task,
        oracle: AcceptanceOracle,
        run_id: UUID,
        outcome: ObservableOutcome,
        is_negative_case: bool,
        worker_run: WorkerRun,
        workspace: Workspace,
        integrated_revision: str,
        guardrail: TestScopeAssessment,
    ) -> tuple[CheckResult, ObservableOutcomeResult, Evidence]:
        spec = _outcome_check_spec(outcome, is_negative_case=is_negative_case)
        check_result = await run_check(self._workspaces, workspace, spec, uow=active)
        evaluated_at = self._clock.now()
        outcome_status = _outcome_status(
            check_result, is_negative_case=is_negative_case
        )

        evidence_content = {
            "outcome_id": str(outcome.outcome_id),
            "check": check_result.model_dump(mode="json"),
            "status": outcome_status,
        }
        content_hash = sha256_hex(canonical_json(evidence_content))
        independence_flags = merge_flags(
            {
                "generator_worker_profile_id": worker_run.worker_profile_id,
                "verifier": "engine.verification.runner",
                "independent": True,
            },
            guardrail,
        )
        signature_payload = {
            "content_hash": content_hash,
            "produced_by": EVIDENCE_PRODUCED_BY,
            "independence_flags": independence_flags,
        }
        evidence = Evidence(
            evidence_id=uuid7(),
            tenant_id=task.tenant_id,
            project_id=task.project_id,
            mission_id=task.mission_id,
            task_id=task.task_id,
            verification_run_id=run_id,
            integrated_revision=integrated_revision,
            oracle_id=oracle.oracle_id,
            outcome_id=outcome.outcome_id,
            evidence_type=spec.kind,
            artifact_refs=[],
            content_hash=content_hash,
            signature=sha256_hex(canonical_json(signature_payload)),
            produced_by=EVIDENCE_PRODUCED_BY,
            independence_flags=independence_flags,
            recorded_at=evaluated_at,
            status=EVIDENCE_STATUS_RECORDED,
            created_at=evaluated_at,
            updated_at=evaluated_at,
        )
        await self._evidence_repository.insert_evidence(active.connection, evidence)

        outcome_result = ObservableOutcomeResult(
            outcome_id=outcome.outcome_id,
            statement=outcome.statement,
            is_negative_case=is_negative_case,
            check_ref=spec.ref,
            status=outcome_status,
            evidence_id=evidence.evidence_id,
            evaluated_at=evaluated_at,
        )
        return check_result, outcome_result, evidence

    def _replay_or_raise(self, record: CommandIdempotency) -> VerificationRun:
        if record.status == "completed" and record.result is not None:
            return VerificationRun.model_validate(record.result)
        if record.status == "failed":
            raise DdeError(
                "VERSION_CONFLICT",
                "Command previously failed; refusing to re-execute",
                details={"idempotency_key": record.idempotency_key},
            )
        raise DdeError(
            "VERSION_CONFLICT",
            "Command is already in progress",
            retryable=True,
            details={"idempotency_key": record.idempotency_key},
        )

    async def get_run(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        verification_run_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> VerificationRun:
        async def _op(active: PostgresUnitOfWork) -> VerificationRun:
            return await self._require_run(active, verification_run_id)

        return await self._run_uow(uow, tenant_id, project_id, _op)

    async def list_evidence(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        verification_run_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[Evidence]:
        async def _op(active: PostgresUnitOfWork) -> list[Evidence]:
            return await self._evidence_repository.list_for_run(
                active.connection, verification_run_id
            )

        return await self._run_uow(uow, tenant_id, project_id, _op)

    async def _require_run(
        self, active: PostgresUnitOfWork, verification_run_id: UUID
    ) -> VerificationRun:
        record = await self._run_repository.get_run(
            active.connection, verification_run_id
        )
        if record is None:
            raise DdeError("POLICY_DENIED", "Unknown verification run")
        return record


def _evaluate(
    *,
    outcome_results: list[ObservableOutcomeResult],
    negative_results: list[ObservableOutcomeResult],
    minimum_confidence: float,
    guardrail: TestScopeAssessment | None = None,
) -> tuple[str, float]:
    """The AcceptanceOracle's own judgment (Chapter 11.1: "AcceptanceOracle
    evaluation"), operating purely on already-collected evidence status --
    it never re-executes a check itself. `PASSED` requires every observable
    outcome to hold, every negative case to NOT hold, and the resulting
    confidence to clear `minimum_confidence`; a single `ERRORED` check means
    the oracle cannot render any verdict at all (a check that could not run
    proves nothing, in either direction).

    Self-grading guardrail: when the pre-oracle sweep recorded a harness-
    gaming violation (undeclared test edits / shadowed expected-test
    layout), a fully-passing outcome set is demoted to `PARTIAL` -- the
    checks ran, but this runner refuses to certify an independent PASS over
    a diff that games them. A failing verdict is left as-is: the guardrail
    never improves a worker's result."""
    all_results = [*outcome_results, *negative_results]
    if not all_results:
        return "ERRORED", 0.0
    if any(item.status == "ERRORED" for item in all_results):
        return "ERRORED", 0.0
    passed = sum(1 for item in all_results if item.status == "PASSED")
    confidence = passed / len(all_results)
    if confidence == 1.0 and confidence >= minimum_confidence:
        if guardrail is not None and guardrail.violations:
            return "PARTIAL", confidence
        return "PASSED", confidence
    if confidence == 0.0:
        return "FAILED", confidence
    return "PARTIAL", confidence
