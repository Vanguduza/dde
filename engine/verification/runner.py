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
`test_scope_violation`). A violating diff still runs the oracle's checks --
but a clean PASS over a harness-gaming diff is not certified as
independent: the run's status is forced to PARTIAL (never PASSED), so
Chapter 6.5 telemetry and downstream integration gates see an untrusted
verdict. The classification then rides the existing recovery surface: the
run's `TaskAttempt` is durably FAILED with `failure_class="SCOPE_VIOLATION"`
(`_fail_unverified_attempt`, the same writer the FAILED branch uses), so
Chapter 12.3's matrix row engages through its existing consumer --
`RecoveryService.assert_clear_to_retry` (`engine.recovery.dispatch`) calls
`decide("SCOPE_VIOLATION")` before any new WorkerRun: action `reject`,
`requires_human`, `allow_new_worker_run=False` -- never a silent retry.

**Confidence bands and the elapsed control (mid-band semantics).**
`_evaluate`'s verdict bands are exact: 1.0 is a certified PASS (every
outcome holds, no violation, `minimum_confidence` cleared -- the elapsed
control can never touch a certified value), 0.0 is FAILED, and everything
between is PARTIAL, graded by construction: above 0.5 the majority of
outcomes hold (near-pass for repair-scope reading), below 0.5 a minority
(near-fail), exactly 0.5 left deliberately uninterpreted. Downstream this
mapping is already total: Chapter 12.3's matrix keys on failure-class
strings only (`engine.recovery.matrix.decide`) and Chapter 6.5 telemetry
admits only PASSED/FAILED, so PARTIAL's graded semantics live entirely in
the persisted confidence value itself.

Within that PARTIAL band an elapsed control erodes confidence
mechanically: each check's real captured `duration_ms` pressure against
the check timeout (`CHECK_TIMEOUT_MS`, from the check runner's default)
starts at `ELAPSED_DEGRADE_ONSET_FRACTION` of the deadline and grows
linearly to full pressure AT the deadline; the mean excess pressure
across checks scales a haircut of at most `ELAPSED_PENALTY_MAX_FRACTION`
off the raw pass ratio. The control is degrade-only: it applies inside
the mid band alone and can never demote a would-be PASS or lift anything
out of FAILED -- mirroring the guardrail rule that findings never improve
a worker's result. Absence of timing data leaves every verdict and value
unchanged.
Still disclosed: the PARTIAL `VerificationRun` gets no
`routing_decision_outcomes` telemetry row (Chapter 6.5's
`actual_verified_outcome` enum admits only PASSED/FAILED, and
`RoutingTelemetryService.record_decision_outcome` gates on terminal
PASSED/FAILED status); per EDR-0009 (accepted 2026-08-23) that gap is
closed on its own surface -- every demotion is durably recorded in
`verification_run_demotions` (same transaction) with its source,
failure class and confidence, so consumers join on `verification_run_id`
instead of the enum being widened. Context-attribution for the violation
is not computed, and automated workspace quarantine remain deferred.

**Flaky-check quarantine (adoption #7).** Every terminal run refreshes
flaky detection over the task's ordered history in the same transaction
as its own terminal write (`FlakyQuarantineService.refresh_quarantines`);
a check whose verdict alternated PASSED/FAILED across runs is durably
quarantined (`flaky_quarantines`, migration 0010). On a FAILED run, the
two-tier gate consults active quarantines first: while the cadence says
wait, the recovery event records `action="deferred_flaky_quarantine"`
instead of the matrix row -- surfaced, never silently swallowed; on an
Nth-run or interval re-entry the plain VERIFICATION_FAILURE decision
applies again. Quarantine never deletes anything; only an operator lift
(`lift`) deactivates a marker.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Final, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.attribution.service import FailureAttributionService
from engine.capabilities.browser import BrowserCapability
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
from engine.verification.checks import (
    DEFAULT_CHECK_TIMEOUT_SECONDS,
    CheckSpec,
    run_check,
)
from engine.verification.demotions import (
    VerificationRunDemotionService,
    source_for,
)
from engine.verification.flaky_quarantine import FlakyQuarantineService
from engine.verification.guardrails import (
    TestScopeAssessment,
    TestScopeFinding,
    assess_diff_independence,
    merge_flags,
)
from engine.verification.prototypes import (
    PrototypeAssessment,
    assess_prototype_dir,
    merge_prototype_flags,
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

#: Effective ceiling for one oracle check: `run()` executes every check via
#: `WorkspaceService.execute` with the check runner's default timeout, so
#: this -- not the workspace layer's own default -- is the deadline the
#: elapsed control measures pressure against.
CHECK_TIMEOUT_MS: Final[float] = DEFAULT_CHECK_TIMEOUT_SECONDS * 1000.0

#: Point of `CHECK_TIMEOUT_MS` beyond which a check's runtime starts to
#: erode its evidentiary weight; at or below it, duration carries no penalty.
ELAPSED_DEGRADE_ONSET_FRACTION: Final[float] = 0.75

#: Largest fraction of the raw pass ratio removable when every check ran to
#: the timeout (mean excess pressure of 1.0).
ELAPSED_PENALTY_MAX_FRACTION: Final[float] = 0.5


def _excess_elapsed_pressure(
    duration_ms: int,
    *,
    timeout_ms: float,
    onset_fraction: float,
) -> float:
    """Linear 0->1 pressure over the onset..timeout span of one check's
    real runtime; 0 at or below the onset point. Pure: no clock access."""
    if timeout_ms <= 0.0:
        return 0.0
    pressure = min(max(duration_ms, 0) / timeout_ms, 1.0)
    if pressure <= onset_fraction:
        return 0.0
    return min((pressure - onset_fraction) / (1.0 - onset_fraction), 1.0)


def _elapsed_penalty_factor(
    durations_ms: Sequence[int],
    *,
    timeout_ms: float,
    onset_fraction: float,
    max_penalty_fraction: float,
) -> float:
    """Multiplicative confidence factor in
    `[1 - max_penalty_fraction, 1]`: the mean excess pressure over all
    checks scales the maximum haircut. No data -> 1.0 (absence of timing
    evidence never moves a verdict)."""
    if not durations_ms:
        return 1.0
    pressures = [
        _excess_elapsed_pressure(
            item, timeout_ms=timeout_ms, onset_fraction=onset_fraction
        )
        for item in durations_ms
    ]
    mean_excess = sum(pressures) / len(pressures)
    return 1.0 - max_penalty_fraction * mean_excess


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
        flaky_quarantine: FlakyQuarantineService | None = None,
        demotions: VerificationRunDemotionService | None = None,
        browser: BrowserCapability | None = None,
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
        # Adoption #7 wiring: the runner owns flaky detection (Chapter
        # 3.6: verification owns the surface a flaky check pollutes).
        self._flaky_quarantine = flaky_quarantine or FlakyQuarantineService(
            engine, events=self._events, clock=self._clock
        )
        # EDR-0009 wiring: the runner owns the demotion record (same
        # guarded path that forces PARTIAL writes the durable trace).
        self._demotions = demotions or VerificationRunDemotionService(
            engine, events=self._events
        )
        # DDE-043/044: Playwright lives in adapters/; inject the capability
        # here so this module never imports a vendor SDK.
        self._browser = browser

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
            # evidence row this run produces. The prototype-manifest sweep
            # (playbook §5.3, guardrail 16) runs in the same pre-oracle
            # slot: real reads over the workspace's prototypes/ directory.
            guardrail = await self._assess_guardrails(
                active,
                task=task,
                oracle=oracle,
                workspace=workspace,
            )
            prototype_check = await self._assess_prototypes(
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
                    prototype_check=prototype_check,
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
                    prototype_check=prototype_check,
                )
                check_results.append(result)
                negative_results.append(outcome_result)
                evidence_refs.append(ev.evidence_id)

            status, confidence = _evaluate(
                outcome_results=outcome_results,
                negative_results=negative_results,
                minimum_confidence=oracle.minimum_confidence,
                guardrail=guardrail,
                prototype_check=prototype_check,
                check_durations_ms=[item.duration_ms for item in check_results],
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
                # Adoption #7: every terminal run refreshes flaky
                # detection, in the same transaction as the run's own
                # terminal write. A newly alternating check ref is durably
                # quarantined here -- never retried into green.
                await self._flaky_quarantine.refresh_quarantines(
                    task=task,
                    runs=prior,
                    uow=active,
                )
            elif next_status == "PARTIAL" and (
                guardrail.violations or prototype_check.violations
            ):
                # A clean check-set over a harness-gaming diff is demoted
                # to PARTIAL and classified SCOPE_VIOLATION on the surface
                # the recovery path already reads: the TaskAttempt is
                # durably FAILED with that failure class (same writer as
                # the FAILED branch), so RecoveryService.
                # assert_clear_to_retry's decide("SCOPE_VIOLATION") row --
                # reject, requires_human, allow_new_worker_run=False --
                # engages without any new state. The run itself stays
                # PARTIAL (append-only terminal status), and no telemetry
                # outcome row exists for it: Chapter 6.5's
                # actual_verified_outcome enum admits only PASSED/FAILED.
                # A prototype-manifest violation (playbook §5.3) demotes
                # identically but classifies as plain VERIFICATION_FAILURE:
                # a broken manifest is ordinary failed verification, not
                # harness gaming -- no new recovery-matrix row invented.
                # EDR-0009: the demotion itself gains a durable, queryable
                # identity in `verification_run_demotions`, written in THIS
                # transaction -- the Chapter 6.5 gap (demoted runs silently
                # absent from decision-outcome history) closes without
                # touching that schema.
                failure_class = (
                    "SCOPE_VIOLATION"
                    if guardrail.violations
                    else "VERIFICATION_FAILURE"
                )
                await self._demotions.record(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission_id=task.mission_id,
                    task_id=task.task_id,
                    worker_run_id=worker_run.run_id,
                    verification_run_id=finished.verification_run_id,
                    source=source_for(guardrail.violations),
                    failure_class=failure_class,
                    confidence=float(finished.confidence),
                    uow=active,
                )
                await self._fail_unverified_attempt(
                    active,
                    task=task,
                    worker_run=worker_run,
                    workspace=workspace,
                    verification_run_id=finished.verification_run_id,
                    failure_class=failure_class,
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
                        "action": "reject",
                        "requires_replan": False,
                        "allow_new_worker_run": False,
                        "failure_class": failure_class,
                        "occurrence_count": 0,
                        "source": (
                            "guardrail_test_scope_violation"
                            if guardrail.violations
                            else "prototype_manifest_violation"
                        ),
                    },
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
                # Adoption #7 two-tier gate: a quarantined ref's failure
                # does not escalate recovery while the cadence says wait;
                # on an Nth-run/interval re-entry (or for never-quarantined
                # refs) the plain VERIFICATION_FAILURE row applies.
                # `count` includes the current run, so the Nth-run cadence
                # fires exactly when THIS failure is the Nth terminal run
                # since detection -- tier two is a real, evaluated gate,
                # not a permanent amnesty. Detection refresh runs in the
                # same transaction as the FAILED write either way.
                deferred_refs = await self._flaky_quarantine.deferred_failure_refs(
                    task=task,
                    runs=prior,
                    failed_check_refs=self._failed_check_refs(finished),
                    uow=active,
                )
                await self._flaky_quarantine.refresh_quarantines(
                    task=task, runs=prior, uow=active
                )
                if deferred_refs:
                    await self._events.append(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        event_type="VerificationFailureRecovery",
                        aggregate_type="verification_run",
                        aggregate_id=finished.verification_run_id,
                        mission_id=task.mission_id,
                        task_id=task.task_id,
                        payload={
                            "action": "deferred_flaky_quarantine",
                            "requires_replan": False,
                            "allow_new_worker_run": True,
                            "failure_class": "VERIFICATION_FAILURE",
                            "occurrence_count": count,
                            "source": "flaky_quarantine_tier_one",
                            "deferred_check_refs": sorted(deferred_refs),
                        },
                        uow=active,
                    )
                else:
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

    async def _assess_prototypes(
        self,
        *,
        workspace: Workspace,
    ) -> PrototypeAssessment:
        """Playbook §5.3: real reads over the workspace's prototypes/
        directory, same pre-oracle slot as the guardrail sweep. Like the
        guardrail diff read, this is a direct workspace *read* on DDE's own
        behalf inside the verification chain -- not a worker-requested
        capability operation and no external-effect journal entry."""
        if not workspace.workspace_path:
            return PrototypeAssessment(findings=())
        try:
            return await asyncio.to_thread(
                assess_prototype_dir, Path(workspace.workspace_path)
            )
        except OSError:
            return PrototypeAssessment(findings=())

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
        failure_class: str = "VERIFICATION_FAILURE",
    ) -> None:
        """Chapter 12.3: VERIFICATION_FAILURE is a durable FAILED attempt,
        not an IN_PROGRESS row that a later invoke_run could treat as a
        first attempt. Failing evidence lives on the VerificationRun.
        Also the classification writer for the guardrail path: a
        guardrail-demoted PARTIAL run lands here with
        `failure_class="SCOPE_VIOLATION"` so Chapter 12.3's never-silent-
        retry row engages through `RecoveryService.assert_clear_to_retry`.
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
            known_failures=[failure_class],
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
            failure_class=failure_class,
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
        prototype_check: PrototypeAssessment,
    ) -> tuple[CheckResult, ObservableOutcomeResult, Evidence]:
        spec = _outcome_check_spec(outcome, is_negative_case=is_negative_case)
        check_result = await run_check(
            self._workspaces,
            workspace,
            spec,
            uow=active,
            browser=self._browser,
        )
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
        independence_flags = merge_prototype_flags(
            merge_flags(
                {
                    "generator_worker_profile_id": worker_run.worker_profile_id,
                    "verifier": "engine.verification.runner",
                    "independent": True,
                },
                guardrail,
            ),
            prototype_check,
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

    @staticmethod
    def _failed_check_refs(run: VerificationRun) -> list[str]:
        """Check refs this run's captured results actually failed."""
        return [
            result.check_ref
            for result in run.check_results
            if result.status == "FAILED"
        ]


def _evaluate(
    *,
    outcome_results: list[ObservableOutcomeResult],
    negative_results: list[ObservableOutcomeResult],
    minimum_confidence: float,
    guardrail: TestScopeAssessment | None = None,
    prototype_check: PrototypeAssessment | None = None,
    check_durations_ms: Sequence[int] | None = None,
    timeout_ms: float = CHECK_TIMEOUT_MS,
) -> tuple[str, float]:
    """The AcceptanceOracle's own judgment (Chapter 11.1: "AcceptanceOracle
    evaluation"), operating purely on already-collected evidence status --
    it never re-executes a check itself. `PASSED` requires every observable
    outcome to hold, every negative case to NOT hold, and the resulting
    confidence to clear `minimum_confidence`; a single `ERRORED` check means
    the oracle cannot render any verdict at all (a check that could not run
    proves nothing, in either direction).

    Confidence bands (deterministic, load-independent; downstream
    `RecoveryService.assert_clear_to_retry` -> `recovery.matrix.decide`
    reads only failure-class strings and Chapter 6.5 telemetry admits only
    PASSED/FAILED, so these bands are the whole PARTIAL contract):

    - 1.0 -- certified pass. Every check PASSED (negative cases FAILED as
      expected), no guardrail/prototype violation, confidence clears
      `minimum_confidence`. The elapsed control below can NEVER touch this
      value: certification is exact.
    - 0.0 -- every check failed: near-certain product truth is false.
    - (0.0, 1.0) -- PARTIAL, graded by construction:
      - high-water (> 0.5): majority of outcomes hold; behaves near-pass
        for any human reading of repair scope.
      - low-water (< 0.5): minority hold; behaves near-fail.
      - exactly 0.5 is the boundary, deliberately left uninterpreted.

    Elapsed control (degrade-only, mechanical): each check's real
    `duration_ms` pressure against `timeout_ms` starts at
    `ELAPSED_DEGRADE_ONSET_FRACTION` of the deadline and grows linearly to
    full pressure AT the deadline; the mean excess pressure across checks
    scales a haircut of at most `ELAPSED_PENALTY_MAX_FRACTION` off the raw
    ratio. The penalty applies ONLY inside the PARTIAL band -- it can
    deepen a mid-band value toward 0 but can never demote a would-be
    PASSED verdict or lift anything out of FAILED, mirroring the
    guardrail's rule that findings never improve a worker's result.
    Durations are optional (`None`: factor 1.0) so absence of timing data
    leaves every existing verdict and value bit-identical.

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
    raw_ratio = passed / len(all_results)
    if raw_ratio == 1.0 and raw_ratio >= minimum_confidence:
        if guardrail is not None and guardrail.violations:
            return "PARTIAL", raw_ratio
        if prototype_check is not None and prototype_check.violations:
            return "PARTIAL", raw_ratio
        return "PASSED", raw_ratio
    if raw_ratio == 0.0:
        return "FAILED", raw_ratio
    # Mid band only: degrade-only erosion of the persisted confidence.
    factor = _elapsed_penalty_factor(
        check_durations_ms or [],
        timeout_ms=timeout_ms,
        onset_fraction=ELAPSED_DEGRADE_ONSET_FRACTION,
        max_penalty_fraction=ELAPSED_PENALTY_MAX_FRACTION,
    )
    return "PARTIAL", min(raw_ratio * factor, raw_ratio)
