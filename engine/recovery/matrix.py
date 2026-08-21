"""Chapter 12.3 failure taxonomy and recovery matrix (DDE-024).

Pure policy: no I/O. Production mutation sites must call `decide()`
before creating a new WorkerRun or treating a retry as legal.
`TaskPlanner.replan` / `RecoveryService.replan` use `classify_dispositions`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from engine.core.errors import DdeError

FAILURE_CLASSES: Final[frozenset[str]] = frozenset(
    {
        "CONTEXT_FAILURE",
        "PLANNING_FAILURE",
        "ROUTING_FAILURE",
        "AUTHORIZATION_FAILURE",
        "ENVIRONMENT_FAILURE",
        "WORKER_FAILURE",
        "TOOL_FAILURE",
        "MERGE_CONFLICT",
        "SCOPE_VIOLATION",
        "VERIFICATION_FAILURE",
        "WRONG_PRODUCT",
        "SPECIFICATION_FAILURE",
        "RESOURCE_EXHAUSTION",
        "SIDE_EFFECT_UNKNOWN",
        "DRIFT_FAILURE",
    }
)

#: Worker/adapter codes that are not Chapter 12.3 names. A new WorkerRun
#: using one of these still hits the same matrix row.
FAILURE_CLASS_ALIASES: Final[dict[str, str]] = {
    "WORKER_COMMAND_FAILED": "WORKER_FAILURE",
    "WORKER_PREPARE_FAILED": "WORKER_FAILURE",
    "WORKER_FAILURE": "WORKER_FAILURE",
    "WORKER_CAPABILITY_DENIED": "AUTHORIZATION_FAILURE",
    "SIDE_EFFECT_UNKNOWN": "SIDE_EFFECT_UNKNOWN",
    "EFFECT_UNKNOWN": "SIDE_EFFECT_UNKNOWN",
    "EFFECT_CONFLICT": "SIDE_EFFECT_UNKNOWN",
    "SCOPE_VIOLATION": "SCOPE_VIOLATION",
    "MERGE_CONFLICT": "MERGE_CONFLICT",
    "WRONG_PRODUCT": "WRONG_PRODUCT",
    "VERIFICATION_FAILED": "VERIFICATION_FAILURE",
    "ORACLE_UNSATISFIED": "VERIFICATION_FAILURE",
    "NO_ELIGIBLE_WORKER": "ROUTING_FAILURE",
    "ROUTE_REJECTED": "ROUTING_FAILURE",
    "ENVIRONMENT_FAILED": "ENVIRONMENT_FAILURE",
    "BUDGET_EXCEEDED": "RESOURCE_EXHAUSTION",
    "QUOTA_EXCEEDED": "RESOURCE_EXHAUSTION",
    "DECOMPOSITION_REQUIRED": "PLANNING_FAILURE",
    "CONTEXT_INCOMPLETE": "CONTEXT_FAILURE",
    "CONTEXT_CONTRADICTION": "CONTEXT_FAILURE",
}

MATRIX_VERSION: Final = "recovery-matrix-v1"

#: Second WORKER_FAILURE is "repeated" (Chapter 12.3 escalation).
WORKER_FAILURE_REROUTE_AFTER: Final = 2
#: Chapter 12.3 / 10.5: > 2 conflicts on one task → replan.
MERGE_CONFLICT_REPLAN_AFTER: Final = 3
#: Repeated verification failure → replan.
VERIFICATION_REPLAN_AFTER: Final = 2
PLANNING_FAILURE_REPLAN_AFTER: Final = 2
ROUTING_FAILURE_ESCALATE_AFTER: Final = 2

REPLAN_TRIGGERS: Final[frozenset[str]] = frozenset(
    {
        "operator",
        "SPECIFICATION_FAILURE",
        "DRIFT_FAILURE",
        "WRONG_PRODUCT",
        "repeated_verification_failure",
        "accepted_edr",
        "MERGE_CONFLICT",
        "PLANNING_FAILURE",
    }
)

Disposition = Literal["PRESERVE", "QUIESCE", "SUPERSEDE", "RETIRE", "REVERT"]
RecoveryAction = Literal[
    "retry",
    "resume_checkpoint",
    "reroute",
    "replan",
    "repair",
    "reconcile",
    "escalate",
    "reject",
    "recompile",
    "amend_graph",
    "replace_environment",
    "alternate_tool",
    "request_approval",
    "request_budget",
    "clarification",
    "drift_review",
]


@dataclass(frozen=True)
class RecoveryDecision:
    """Internal matrix result (AGENTS.md: dataclass, not a contract)."""

    failure_class: str
    action: RecoveryAction
    allow_new_worker_run: bool
    requires_replan: bool
    requires_human: bool
    error_code: str
    message: str
    retryable: bool
    matrix_version: str = MATRIX_VERSION


def canonical_failure_class(raw: str) -> str:
    token = raw.strip()
    if token in FAILURE_CLASSES:
        return token
    aliased = FAILURE_CLASS_ALIASES.get(token)
    if aliased is not None:
        return aliased
    raise DdeError(
        "POLICY_DENIED",
        "recovery refuses an unknown failure class rather than guessing",
        retryable=False,
        details={"failure_class": raw},
    )


def decide(
    failure_class: str,
    *,
    occurrence_count: int = 1,
    unreconciled: bool = False,
) -> RecoveryDecision:
    """Chapter 12.3 row for this class, plus the escalation column.

    `occurrence_count` is how many times this class has already been
    recorded for the task (including the current failure). `unreconciled`
    is only consulted for `SIDE_EFFECT_UNKNOWN`.
    """
    if occurrence_count < 1:
        raise DdeError(
            "POLICY_DENIED",
            "occurrence_count must be >= 1",
            details={"occurrence_count": occurrence_count},
        )
    canonical = canonical_failure_class(failure_class)
    return _ROW[canonical](occurrence_count, unreconciled)


def _context(occurrence_count: int, unreconciled: bool) -> RecoveryDecision:
    del unreconciled
    return RecoveryDecision(
        failure_class="CONTEXT_FAILURE",
        action="recompile",
        allow_new_worker_run=False,
        requires_replan=False,
        requires_human=occurrence_count >= 2,
        error_code="CONTEXT_INCOMPLETE",
        message="CONTEXT_FAILURE: recompile with expanded retrieval; no worker retry",
        retryable=False,
    )


def _planning(occurrence_count: int, unreconciled: bool) -> RecoveryDecision:
    del unreconciled
    replan = occurrence_count >= PLANNING_FAILURE_REPLAN_AFTER
    return RecoveryDecision(
        failure_class="PLANNING_FAILURE",
        action="replan" if replan else "amend_graph",
        allow_new_worker_run=False,
        requires_replan=replan,
        requires_human=replan,
        error_code="DECOMPOSITION_REQUIRED",
        message="PLANNING_FAILURE: decompose or amend; repeated failure replans",
        retryable=False,
    )


def _routing(occurrence_count: int, unreconciled: bool) -> RecoveryDecision:
    del unreconciled
    escalate = occurrence_count >= ROUTING_FAILURE_ESCALATE_AFTER
    return RecoveryDecision(
        failure_class="ROUTING_FAILURE",
        action="escalate" if escalate else "reroute",
        allow_new_worker_run=False,
        requires_replan=False,
        requires_human=escalate,
        error_code="ROUTE_REJECTED",
        message="ROUTING_FAILURE: re-evaluate route; no silent worker retry",
        retryable=False,
    )


def _authorization(occurrence_count: int, unreconciled: bool) -> RecoveryDecision:
    del occurrence_count, unreconciled
    return RecoveryDecision(
        failure_class="AUTHORIZATION_FAILURE",
        action="request_approval",
        allow_new_worker_run=False,
        requires_replan=False,
        requires_human=True,
        error_code="POLICY_DENIED",
        message="AUTHORIZATION_FAILURE: no silent retry",
        retryable=False,
    )


def _environment(occurrence_count: int, unreconciled: bool) -> RecoveryDecision:
    del occurrence_count, unreconciled
    return RecoveryDecision(
        failure_class="ENVIRONMENT_FAILURE",
        action="replace_environment",
        allow_new_worker_run=False,
        requires_replan=False,
        requires_human=True,
        error_code="ENVIRONMENT_FAILED",
        message=(
            "ENVIRONMENT_FAILURE: replace environment then resume from "
            "checkpoint; refusing a retry on the same environment"
        ),
        retryable=False,
    )


def _worker(occurrence_count: int, unreconciled: bool) -> RecoveryDecision:
    del unreconciled
    repeated = occurrence_count >= WORKER_FAILURE_REROUTE_AFTER
    return RecoveryDecision(
        failure_class="WORKER_FAILURE",
        action="reroute" if repeated else "retry",
        allow_new_worker_run=not repeated,
        requires_replan=False,
        requires_human=repeated,
        error_code="ROUTE_REJECTED" if repeated else "POLICY_DENIED",
        message=(
            "WORKER_FAILURE: repeated failure requires reroute"
            if repeated
            else "WORKER_FAILURE: recover session/run"
        ),
        retryable=not repeated,
    )


def _tool(occurrence_count: int, unreconciled: bool) -> RecoveryDecision:
    del occurrence_count, unreconciled
    return RecoveryDecision(
        failure_class="TOOL_FAILURE",
        action="alternate_tool",
        allow_new_worker_run=False,
        requires_replan=False,
        requires_human=True,
        error_code="POLICY_DENIED",
        message="TOOL_FAILURE: alternate certified implementation required (DDE-025)",
        retryable=False,
    )


def _merge(occurrence_count: int, unreconciled: bool) -> RecoveryDecision:
    del unreconciled
    replan = occurrence_count >= MERGE_CONFLICT_REPLAN_AFTER
    return RecoveryDecision(
        failure_class="MERGE_CONFLICT",
        action="replan" if replan else "repair",
        allow_new_worker_run=False,
        requires_replan=replan,
        requires_human=replan,
        error_code="DECOMPOSITION_REQUIRED" if replan else "MERGE_CONFLICT",
        message=(
            "MERGE_CONFLICT: > 2 conflicts escalate to replan"
            if replan
            else "MERGE_CONFLICT: emit scoped repair task"
        ),
        retryable=False,
    )


def _scope(occurrence_count: int, unreconciled: bool) -> RecoveryDecision:
    del occurrence_count, unreconciled
    return RecoveryDecision(
        failure_class="SCOPE_VIOLATION",
        action="reject",
        allow_new_worker_run=False,
        requires_replan=False,
        requires_human=True,
        error_code="SCOPE_VIOLATION",
        message="SCOPE_VIOLATION: reject and quarantine; never retry",
        retryable=False,
    )


def _verification(occurrence_count: int, unreconciled: bool) -> RecoveryDecision:
    del unreconciled
    replan = occurrence_count >= VERIFICATION_REPLAN_AFTER
    return RecoveryDecision(
        failure_class="VERIFICATION_FAILURE",
        action="replan" if replan else "repair",
        allow_new_worker_run=not replan,
        requires_replan=replan,
        requires_human=replan,
        error_code="VERIFICATION_FAILED",
        message=(
            "VERIFICATION_FAILURE: repeated failure replans"
            if replan
            else (
                "VERIFICATION_FAILURE: repair then re-verify; preserve failing evidence"
            )
        ),
        retryable=not replan,
    )


def _wrong_product(occurrence_count: int, unreconciled: bool) -> RecoveryDecision:
    del occurrence_count, unreconciled
    return RecoveryDecision(
        failure_class="WRONG_PRODUCT",
        action="replan",
        allow_new_worker_run=False,
        requires_replan=True,
        requires_human=True,
        error_code="WRONG_PRODUCT",
        message="WRONG_PRODUCT: replan; no silent retry",
        retryable=False,
    )


def _specification(occurrence_count: int, unreconciled: bool) -> RecoveryDecision:
    del occurrence_count, unreconciled
    return RecoveryDecision(
        failure_class="SPECIFICATION_FAILURE",
        action="clarification",
        allow_new_worker_run=False,
        requires_replan=True,
        requires_human=True,
        error_code="POLICY_DENIED",
        message="SPECIFICATION_FAILURE: never guess; human authority required",
        retryable=False,
    )


def _resource(occurrence_count: int, unreconciled: bool) -> RecoveryDecision:
    del occurrence_count, unreconciled
    return RecoveryDecision(
        failure_class="RESOURCE_EXHAUSTION",
        action="request_budget",
        allow_new_worker_run=False,
        requires_replan=False,
        requires_human=True,
        error_code="BUDGET_EXCEEDED",
        message="RESOURCE_EXHAUSTION: checkpoint and request budget; no new mutation",
        retryable=False,
    )


def _unknown(occurrence_count: int, unreconciled: bool) -> RecoveryDecision:
    del occurrence_count
    return RecoveryDecision(
        failure_class="SIDE_EFFECT_UNKNOWN",
        action="reconcile",
        allow_new_worker_run=not unreconciled,
        requires_replan=False,
        requires_human=unreconciled,
        error_code="EFFECT_UNKNOWN",
        message=(
            "SIDE_EFFECT_UNKNOWN: reconcile before any retry"
            if unreconciled
            else "SIDE_EFFECT_UNKNOWN: reconciled absence permits a new mutation"
        ),
        retryable=not unreconciled,
    )


def _drift(occurrence_count: int, unreconciled: bool) -> RecoveryDecision:
    del occurrence_count, unreconciled
    return RecoveryDecision(
        failure_class="DRIFT_FAILURE",
        action="drift_review",
        allow_new_worker_run=False,
        requires_replan=True,
        requires_human=True,
        error_code="POLICY_DENIED",
        message="DRIFT_FAILURE: stop the mutation path; trigger drift review",
        retryable=False,
    )


_ROW: dict[str, Callable[[int, bool], RecoveryDecision]] = {
    "CONTEXT_FAILURE": _context,
    "PLANNING_FAILURE": _planning,
    "ROUTING_FAILURE": _routing,
    "AUTHORIZATION_FAILURE": _authorization,
    "ENVIRONMENT_FAILURE": _environment,
    "WORKER_FAILURE": _worker,
    "TOOL_FAILURE": _tool,
    "MERGE_CONFLICT": _merge,
    "SCOPE_VIOLATION": _scope,
    "VERIFICATION_FAILURE": _verification,
    "WRONG_PRODUCT": _wrong_product,
    "SPECIFICATION_FAILURE": _specification,
    "RESOURCE_EXHAUSTION": _resource,
    "SIDE_EFFECT_UNKNOWN": _unknown,
    "DRIFT_FAILURE": _drift,
}


def classify_dispositions(
    *,
    task_ids: Sequence[UUID],
    statuses: Mapping[UUID, str],
    in_flight_ids: set[UUID],
    completed_ids: set[UUID],
    integrated_ids: set[UUID],
    trigger: str,
    retire_ids: set[UUID] | None = None,
) -> tuple[dict[str, Disposition], dict[str, str]]:
    """Chapter 4.6 per-node classification.

    Completed/integrated durable results are PRESERVE unless the trigger
    is WRONG_PRODUCT (REVERT). Explicit retire_ids are RETIRE and are never
    inferred from a failure class. In-flight nodes QUIESCE unless the
    trigger invalidates them (SUPERSEDE). Open nodes stay PRESERVE on an
    operator replan and SUPERSEDE when the specification/drift/wrong-product
    invalidates the graph.
    """
    dispositions: dict[str, Disposition] = {}
    explanations: dict[str, str] = {}
    invalidating = trigger in {
        "SPECIFICATION_FAILURE",
        "DRIFT_FAILURE",
        "WRONG_PRODUCT",
        "repeated_verification_failure",
        "accepted_edr",
        "MERGE_CONFLICT",
        "PLANNING_FAILURE",
    }
    retire = retire_ids or set()
    for task_id in task_ids:
        key = str(task_id)
        status = statuses.get(task_id, "CREATED")
        completed = task_id in completed_ids or status == "COMPLETED"
        integrated = task_id in integrated_ids
        in_flight = task_id in in_flight_ids
        if status in {"SUPERSEDED", "RETIRED"}:
            dispositions[key] = "PRESERVE"
            continue
        if completed or integrated:
            if trigger == "WRONG_PRODUCT" and integrated:
                dispositions[key] = "REVERT"
                explanations[key] = (
                    "WRONG_PRODUCT: merged output must be undone by a revert task"
                )
            else:
                dispositions[key] = "PRESERVE"
            continue
        if task_id in retire:
            dispositions[key] = "RETIRE"
            explanations[key] = (
                "explicit RETIRE: node no longer needed; artifacts retained"
            )
            continue
        if in_flight:
            if invalidating:
                dispositions[key] = "SUPERSEDE"
                explanations[key] = (
                    f"{trigger}: in-flight node superseded; attempt results retained"
                )
            else:
                dispositions[key] = "QUIESCE"
            continue
        if invalidating:
            dispositions[key] = "SUPERSEDE"
            explanations[key] = (
                f"{trigger}: open node superseded; durable results retained"
            )
        else:
            dispositions[key] = "PRESERVE"
    return dispositions, explanations
