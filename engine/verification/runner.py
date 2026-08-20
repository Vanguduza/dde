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
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

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
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work
from engine.verification.checks import CheckSpec, run_check
from engine.verification.repository import EvidenceRepository, VerificationRunRepository
from engine.verification.states import VERIFICATION_RUN_TRANSITIONS
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
    ) -> None:
        self._engine = engine
        self._workspaces = workspaces
        self._events = events or EventService(engine)
        self._commands = commands or CommandLedger(engine)
        self._run_repository = run_repository or VerificationRunRepository()
        self._evidence_repository = evidence_repository or EvidenceRepository()
        self._clock = clock or SystemClock()

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
                )
                check_results.append(result)
                negative_results.append(outcome_result)
                evidence_refs.append(ev.evidence_id)

            status, confidence = _evaluate(
                outcome_results=outcome_results,
                negative_results=negative_results,
                minimum_confidence=oracle.minimum_confidence,
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
            await self._commands.complete(
                tenant_id=tenant_id,
                project_id=project_id,
                command_id=record.command_id,
                result=finished.model_dump(mode="json"),
                uow=active,
            )
            return finished

        return await self._run_uow(uow, tenant_id, project_id, _op)

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
        independence_flags = {
            "generator_worker_profile_id": worker_run.worker_profile_id,
            "verifier": "engine.verification.runner",
            "independent": True,
        }
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
) -> tuple[str, float]:
    """The AcceptanceOracle's own judgment (Chapter 11.1: "AcceptanceOracle
    evaluation"), operating purely on already-collected evidence status --
    it never re-executes a check itself. `PASSED` requires every observable
    outcome to hold, every negative case to NOT hold, and the resulting
    confidence to clear `minimum_confidence`; a single `ERRORED` check means
    the oracle cannot render any verdict at all (a check that could not run
    proves nothing, in either direction)."""
    all_results = [*outcome_results, *negative_results]
    if not all_results:
        return "ERRORED", 0.0
    if any(item.status == "ERRORED" for item in all_results):
        return "ERRORED", 0.0
    passed = sum(1 for item in all_results if item.status == "PASSED")
    confidence = passed / len(all_results)
    if confidence == 1.0 and confidence >= minimum_confidence:
        return "PASSED", confidence
    if confidence == 0.0:
        return "FAILED", confidence
    return "PARTIAL", confidence
