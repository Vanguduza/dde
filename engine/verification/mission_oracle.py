"""Chapter 11.3 mission-level AcceptanceOracle evaluation (DDE-037).

`MissionOracleService.evaluate()` is the production mutation: it runs the
mission oracle's real, already-declared executable bindings through the
same `engine.verification.checks.run_check` path task oracles use, reads
the latest task-scope `VerificationRun` per non-retired task, and persists
one `MissionOracleEvaluation`.

WRONG_PRODUCT is recorded only when every non-retired task oracle has
PASSED and the mission oracle itself fails -- never fabricated from a
missing task oracle (that is INCOMPLETE). The recovery matrix's
WRONG_PRODUCT action (replan, no silent worker retry) is attached to the
row; `learning_signal_class=decomposition_quality` names Chapter 11.3's
decomposition-quality signal, and `excluded_from_routing_learning` is
hard-coded True so this row cannot teach the router.

`assert_ready_to_complete` is the Chapter 4.9 / 11.3 completion gate
called from `MissionService.transition_mission` when the target is
COMPLETED.

Not a registered Capability -- internal engine verification, same as
`VerificationRunnerService`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from engine.contracts.acceptance_oracle import ObservableOutcome
from engine.contracts.command_idempotency import CommandIdempotency
from engine.contracts.mission import Mission
from engine.contracts.mission_oracle_evaluation import MissionOracleEvaluation
from engine.contracts.task import Task
from engine.contracts.verification_run import CheckResult, ObservableOutcomeResult
from engine.contracts.workspace import Workspace
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.hashing import canonical_json, sha256_hex
from engine.core.ids import uuid7
from engine.events.idempotency import CommandLedger
from engine.events.service import EventService
from engine.missions.repository import MissionsRepository
from engine.recovery.matrix import RecoveryDecision, decide
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work
from engine.verification.checks import CheckSpec, run_check
from engine.verification.repository import (
    AcceptanceOracleRepository,
    MissionOracleEvaluationRepository,
    VerificationRunRepository,
)
from engine.workspaces.service import WorkspaceService

T = TypeVar("T")

_TERMINAL_SKIP = frozenset({"RETIRED", "SUPERSEDED"})
_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

#: Chapter 11.3's "end-to-end and user-visible" outcomes against a
#: ProductEnvironment are DDE-038; this slice runs the mission oracle's
#: declared test/invariant bindings in the supplied workspace.
_PRODUCT_ENVIRONMENT_GAP = (
    "user-visible ProductEnvironment e2e is DDE-038; this evaluation runs "
    "the mission oracle's declared test/invariant bindings in the supplied "
    "workspace"
)


def _requires_mission_oracle(tasks: list[Task]) -> bool:
    if not tasks:
        return False
    return max(_RISK_ORDER[task.risk_class] for task in tasks) >= _RISK_ORDER["medium"]


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


def _judge_mission_oracle(
    outcome_results: list[ObservableOutcomeResult],
    *,
    minimum_confidence: float,
) -> str:
    if not outcome_results:
        return "ERRORED"
    if any(item.status == "ERRORED" for item in outcome_results):
        return "ERRORED"
    passed = sum(1 for item in outcome_results if item.status == "PASSED")
    confidence = passed / len(outcome_results)
    if confidence == 1.0 and confidence >= minimum_confidence:
        return "PASSED"
    return "FAILED"


def _evaluation_request_hash(
    *, mission_id: UUID, oracle_id: UUID, oracle_version: str, workspace_id: UUID
) -> str:
    return sha256_hex(
        canonical_json(
            {
                "mission_id": str(mission_id),
                "oracle_id": str(oracle_id),
                "oracle_version": oracle_version,
                "workspace_id": str(workspace_id),
            }
        )
    )


def _recovery_json(decision: RecoveryDecision) -> dict[str, object]:
    return {
        "failure_class": decision.failure_class,
        "action": decision.action,
        "allow_new_worker_run": decision.allow_new_worker_run,
        "requires_replan": decision.requires_replan,
        "requires_human": decision.requires_human,
        "error_code": decision.error_code,
        "message": decision.message,
        "retryable": decision.retryable,
    }


async def assert_ready_to_complete(
    connection: AsyncConnection, mission_id: UUID
) -> None:
    """Chapter 4.9 / 11.3: COMPLETED requires a passing mission oracle when
    the mission carries one, and every mission whose tasks reach risk >=
    medium must carry one."""
    tasks = await MissionsRepository().list_tasks_for_mission(connection, mission_id)
    oracles = AcceptanceOracleRepository()
    evaluations = MissionOracleEvaluationRepository()
    oracle = await oracles.get_latest_mission_oracle(connection, mission_id)
    evaluation = await evaluations.get_latest_for_mission(connection, mission_id)
    if evaluation is not None and evaluation.status == "WRONG_PRODUCT":
        raise DdeError(
            "WRONG_PRODUCT",
            "Mission oracle failed after task oracles passed; refusing COMPLETED",
            retryable=False,
            details={"evaluation_id": str(evaluation.evaluation_id)},
        )
    needs_accept = _requires_mission_oracle(tasks) or oracle is not None
    if needs_accept and (evaluation is None or evaluation.status != "ACCEPT"):
        raise DdeError(
            "ORACLE_UNSATISFIED",
            "Chapter 11.3: mission completion requires a passing mission "
            "AcceptanceOracle",
            retryable=False,
            details={
                "mission_id": str(mission_id),
                "has_mission_oracle": oracle is not None,
                "evaluation_status": None if evaluation is None else evaluation.status,
            },
        )


class MissionOracleService:
    """Async PostgreSQL writer for `mission_oracle_evaluations`."""

    def __init__(
        self,
        engine: AsyncEngine,
        workspaces: WorkspaceService,
        events: EventService | None = None,
        commands: CommandLedger | None = None,
        oracles: AcceptanceOracleRepository | None = None,
        evaluations: MissionOracleEvaluationRepository | None = None,
        verification_runs: VerificationRunRepository | None = None,
        missions: MissionsRepository | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._workspaces = workspaces
        self._events = events or EventService(engine)
        self._commands = commands or CommandLedger(engine)
        self._oracles = oracles or AcceptanceOracleRepository()
        self._evaluations = evaluations or MissionOracleEvaluationRepository()
        self._runs = verification_runs or VerificationRunRepository()
        self._missions = missions or MissionsRepository()
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

    async def _task_oracle_verdict(
        self, connection: AsyncConnection, tasks: list[Task]
    ) -> Literal["all_passed", "incomplete", "task_failed"]:
        active = [task for task in tasks if task.status not in _TERMINAL_SKIP]
        passed_any = False
        for task in active:
            task_oracles = await self._oracles.list_task_oracles(
                connection, task.task_id
            )
            if not task_oracles:
                continue
            runs = await self._runs.list_for_task(connection, task.task_id)
            if not runs:
                return "incomplete"
            latest = runs[-1]
            if latest.status == "FAILED":
                return "task_failed"
            if latest.status != "PASSED":
                return "incomplete"
            passed_any = True
        if not passed_any:
            return "incomplete"
        return "all_passed"

    async def evaluate(
        self,
        *,
        mission: Mission,
        workspace: Workspace,
        idempotency_key: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> MissionOracleEvaluation:
        tenant_id = mission.tenant_id
        project_id = mission.project_id

        async def _op(active: PostgresUnitOfWork) -> MissionOracleEvaluation:
            oracle = await self._oracles.get_latest_mission_oracle(
                active.connection, mission.mission_id
            )
            if oracle is None:
                raise DdeError(
                    "ORACLE_UNSATISFIED",
                    "No mission-scope AcceptanceOracle is defined for this mission",
                    retryable=False,
                    details={"mission_id": str(mission.mission_id)},
                )
            request_hash = _evaluation_request_hash(
                mission_id=mission.mission_id,
                oracle_id=oracle.oracle_id,
                oracle_version=oracle.oracle_version,
                workspace_id=workspace.workspace_id,
            )
            record, is_new = await self._commands.begin(
                tenant_id=tenant_id,
                project_id=project_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                uow=active,
            )
            if not is_new:
                return self._replay_or_raise(record)

            tasks = await self._missions.list_tasks_for_mission(
                active.connection, mission.mission_id
            )
            task_verdict = await self._task_oracle_verdict(active.connection, tasks)

            check_results: list[CheckResult] = []
            outcome_results: list[ObservableOutcomeResult] = []
            now = self._clock.now()
            pairs: list[tuple[ObservableOutcome, bool]] = [
                *[(item, False) for item in oracle.observable_outcomes],
                *[(item, True) for item in oracle.negative_cases],
            ]
            for outcome, is_negative in pairs:
                spec = _outcome_check_spec(outcome, is_negative_case=is_negative)
                check = await run_check(self._workspaces, workspace, spec, uow=active)
                check_results.append(check)
                outcome_results.append(
                    ObservableOutcomeResult(
                        outcome_id=outcome.outcome_id,
                        statement=outcome.statement,
                        is_negative_case=is_negative,
                        check_ref=spec.ref,
                        status=_outcome_status(check, is_negative_case=is_negative),
                        evidence_id=None,
                        evaluated_at=self._clock.now(),
                    )
                )

            mission_result = _judge_mission_oracle(
                outcome_results, minimum_confidence=oracle.minimum_confidence
            )
            if mission_result == "ERRORED":
                status: Literal["ACCEPT", "WRONG_PRODUCT", "INCOMPLETE", "ERRORED"] = (
                    "ERRORED"
                )
            elif task_verdict != "all_passed":
                status = "INCOMPLETE"
            elif mission_result == "PASSED":
                status = "ACCEPT"
            else:
                status = "WRONG_PRODUCT"

            recovery: dict[str, object] | None = None
            learning: Literal["decomposition_quality", "none"] = "none"
            if status == "WRONG_PRODUCT":
                recovery = _recovery_json(decide("WRONG_PRODUCT"))
                learning = "decomposition_quality"

            evaluation = MissionOracleEvaluation(
                evaluation_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission.mission_id,
                oracle_id=oracle.oracle_id,
                workspace_id=workspace.workspace_id,
                status=status,
                task_oracle_verdict=task_verdict,
                check_results=[item.model_dump(mode="json") for item in check_results],
                outcome_results=[
                    item.model_dump(mode="json") for item in outcome_results
                ],
                recovery_decision=recovery,
                learning_signal_class=learning,
                excluded_from_routing_learning=True,
                disclosed_gaps=[_PRODUCT_ENVIRONMENT_GAP],
                created_at=now,
                updated_at=self._clock.now(),
            )
            await self._evaluations.insert_evaluation(active.connection, evaluation)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="MissionOracleEvaluated",
                aggregate_type="mission_oracle_evaluation",
                aggregate_id=evaluation.evaluation_id,
                mission_id=mission.mission_id,
                task_id=None,
                payload={
                    "status": status,
                    "task_oracle_verdict": task_verdict,
                    "learning_signal_class": learning,
                },
                uow=active,
            )
            await self._commands.complete(
                tenant_id=tenant_id,
                project_id=project_id,
                command_id=record.command_id,
                result=evaluation.model_dump(mode="json"),
                uow=active,
            )
            return evaluation

        return await self._run(uow, tenant_id, project_id, _op)

    def _replay_or_raise(self, record: CommandIdempotency) -> MissionOracleEvaluation:
        if record.status == "completed" and record.result is not None:
            return MissionOracleEvaluation.model_validate(record.result)
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
