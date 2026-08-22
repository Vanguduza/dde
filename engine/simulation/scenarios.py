"""Chapter 6.4's real, deterministic adversarial fixture generator.

`engine.routing.rules.evaluate()` is a pure function of a `Task` plus a
handful of caller-supplied overrides (`certification_statuses`,
`previous_generator_profile_id`, `routing_environment_class`,
`approval_satisfied`) -- it never touches the database (Chapter 6.1's
gates 0-5 run entirely against real, already-declared policy and
registry data: `engine.routing.policy`/`engine.routing.registry`). This
module drives that same real pipeline with synthetic, seeded `Task`
inputs to produce genuine adversarial routing outcomes for regression
and stress testing (Chapter 6.4), never a hand-parameterised probability
model and never a call into `engine.routing.service.RouterService.route()`
-- the RSM must never write a real, authoritative `RouteDecision` row.

**Real scenario classes** (`REAL_SCENARIO_CLASSES`). Each drives a
genuine elimination already implemented in `engine.routing.rules`:

- `worker_outage` -- every profile `engine.routing.policy` prefers for
  `bulk_implementation` is marked `REVOKED` in a non-development
  environment (`allow_stale=False`), so gate 3 (`worker_eligibility`)
  eliminates every one of them for real (`NOT_CERTIFIED_FOR_WORKLOAD`),
  exactly Chapter 6.1's gate-3 "certified profiles that can satisfy 1+2"
  check failing outage-wide.
- `generator_independence_violation` -- a `verification` task whose
  `previous_generator_profile_id` equals the only profile
  `verification`'s policy prefers (`profile.deterministic_runner`,
  `forbid_generator=True`) -- Chapter 11.4's real independence rule
  (`GENERATOR_INDEPENDENCE_VIOLATION`) eliminates the sole candidate.
- `hard_gate_approval_required` -- `task.requires_approval=True` with
  `approval_satisfied=False` -- Chapter 6.1 gate 0's real hard-policy
  elimination (`HARD_GATE_APPROVAL_REQUIRED`), applied before any
  candidate is even considered.

All three are real, already-implemented elimination paths; this module
never fabricates a new one to reach a scenario name.

**Deferred scenario classes** (`DEFERRED_SCENARIO_CLASSES`), named
honestly rather than silently unsupported -- see
`docs/truth/edr/EDR-0006-routing-simulation-fixture-generator-partial-scope.md`
for the full reasoning:

- `capability_gap` / `environment_incompatibility` -- Stage 1's real,
  fixed worker-profile registry (`engine.routing.registry.PROFILES`) is
  constructed so every workload class's own preferred profile already
  satisfies that class's declared capability/environment requirement
  (`engine.routing.policy.WORKLOAD_CLASSES`) -- there is no real
  candidate set in this codebase today whose *entire* preferred set
  fails gate 1 or gate 4, and fabricating a registry entry that lacks a
  capability it does not really lack would misrepresent a certified
  profile, not simulate an outage of one.
- `modality_mismatch` -- Stage 1 has no per-task modality signal at all
  (Chapter 5.2's Visual retriever is unbuilt until Stage 5, DDE-044); a
  "mismatch" needs two real modality values to compare, and only one
  (the profile's declared capabilities) exists.
- `budget_exhaustion` -- gate 5 (`capacity_availability`) is a real,
  disclosed, hard-coded pass-through (`AVAILABILITY_NOT_TRACKED`,
  `engine.routing.rules`'s own comment) with no worker health/quota/
  concurrency/budget signal behind it yet (Chapter 8 Worker Manager,
  DDE-011/029) -- there is no real signal to exhaust.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from engine.contracts.task import Task
from engine.core.errors import DdeError
from engine.routing.policy import WORKLOAD_CLASSES
from engine.routing.rules import RoutingResult, evaluate

SCENARIO_WORKER_OUTAGE = "worker_outage"
SCENARIO_GENERATOR_INDEPENDENCE_VIOLATION = "generator_independence_violation"
SCENARIO_HARD_GATE_APPROVAL_REQUIRED = "hard_gate_approval_required"

REAL_SCENARIO_CLASSES: tuple[str, ...] = (
    SCENARIO_WORKER_OUTAGE,
    SCENARIO_GENERATOR_INDEPENDENCE_VIOLATION,
    SCENARIO_HARD_GATE_APPROVAL_REQUIRED,
)

#: Named honestly, never silently unsupported. See the module docstring
#: and EDR-0006 for the real reason each cannot be generated for real
#: against Stage 1's fixed registry and gate implementations.
DEFERRED_SCENARIO_CLASSES: tuple[str, ...] = (
    "capability_gap",
    "modality_mismatch",
    "budget_exhaustion",
    "environment_incompatibility",
)

#: A fixed, versioned UUID namespace so `uuid.uuid5(namespace, seed)` is
#: reproducible across processes and Python versions -- Chapter 6.4:
#: "simulation seeds ... are persisted for reproducibility."
_SEED_NAMESPACE = uuid.UUID("6f1a6b2e-6c5b-4b0e-9c3a-2b6b9b2b6b2b")


@dataclass(frozen=True)
class ScenarioFixture:
    """A real, seeded `Task` plus the exact `evaluate()` call arguments
    this scenario class drives -- never invoked against
    `RouterService.route()`, so no real `RouteDecision` is ever written."""

    scenario_class: str
    task: Task
    workload_class: str | None
    previous_generator_profile_id: str | None
    certification_statuses: dict[str, str] | None
    routing_environment_class: str
    approval_satisfied: bool
    expected_reason_code: str


def _deterministic_uuid(seed: str, *parts: str) -> UUID:
    return uuid.uuid5(_SEED_NAMESPACE, ":".join((seed, *parts)))


def _base_task(
    *,
    seed: str,
    scenario_class: str,
    tenant_id: UUID,
    project_id: UUID,
    task_class: str,
    risk_class: str,
    requires_approval: bool,
) -> Task:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    task_id = _deterministic_uuid(seed, scenario_class, "task")
    mission_id = _deterministic_uuid(seed, scenario_class, "mission")
    graph_id = _deterministic_uuid(seed, scenario_class, "graph")
    return Task(
        task_id=task_id,
        tenant_id=tenant_id,
        project_id=project_id,
        mission_id=mission_id,
        graph_id=graph_id,
        title=f"RSM fixture: {scenario_class}",
        intent=f"Chapter 6.4 adversarial routing fixture ({scenario_class})",
        task_class=task_class,
        requirement_refs=[],
        feature_refs=[],
        success_criteria=["Router escalates to HUMAN_DECISION_TASK"],
        expected_write_scope=[],
        expected_read_scope=[],
        blast_radius="local",
        risk_class=risk_class,
        estimated_effort="xs",
        autonomy_ceiling=1,
        requires_approval=requires_approval,
        verification_profile_ref=None,
        status="CREATED",
        lock_version=1,
        created_at=now,
        updated_at=now,
    )


def build_fixture(
    scenario_class: str, *, seed: str, tenant_id: UUID, project_id: UUID
) -> ScenarioFixture:
    """Build the real, deterministic `evaluate()` inputs for
    `scenario_class`. Raises `DdeError` for any class this module does
    not (or cannot honestly) generate a real fixture for -- never
    silently substitutes a placeholder result."""
    if scenario_class in DEFERRED_SCENARIO_CLASSES:
        raise DdeError(
            "POLICY_DENIED",
            "scenario class has no real, un-fabricated fixture in Stage 1 "
            "-- see EDR-0006-routing-simulation-fixture-generator-partial-scope",
            retryable=False,
            details={"scenario_class": scenario_class},
        )
    if scenario_class == SCENARIO_WORKER_OUTAGE:
        task = _base_task(
            seed=seed,
            scenario_class=scenario_class,
            tenant_id=tenant_id,
            project_id=project_id,
            task_class="implementation",
            risk_class="low",
            requires_approval=False,
        )
        revoked = {
            profile_id: "REVOKED"
            for profile_id in WORKLOAD_CLASSES["bulk_implementation"].prefer
        }
        return ScenarioFixture(
            scenario_class=scenario_class,
            task=task,
            workload_class="bulk_implementation",
            previous_generator_profile_id=None,
            certification_statuses=revoked,
            routing_environment_class="production",
            approval_satisfied=True,
            expected_reason_code="NO_ELIGIBLE_WORKER",
        )
    if scenario_class == SCENARIO_GENERATOR_INDEPENDENCE_VIOLATION:
        task = _base_task(
            seed=seed,
            scenario_class=scenario_class,
            tenant_id=tenant_id,
            project_id=project_id,
            task_class="verification",
            risk_class="low",
            requires_approval=False,
        )
        sole_preferred = WORKLOAD_CLASSES["verification"].prefer[0]
        return ScenarioFixture(
            scenario_class=scenario_class,
            task=task,
            workload_class="verification",
            previous_generator_profile_id=sole_preferred,
            certification_statuses=None,
            routing_environment_class="development",
            approval_satisfied=True,
            expected_reason_code="NO_ELIGIBLE_WORKER",
        )
    if scenario_class == SCENARIO_HARD_GATE_APPROVAL_REQUIRED:
        task = _base_task(
            seed=seed,
            scenario_class=scenario_class,
            tenant_id=tenant_id,
            project_id=project_id,
            task_class="implementation",
            risk_class="high",
            requires_approval=True,
        )
        return ScenarioFixture(
            scenario_class=scenario_class,
            task=task,
            workload_class=None,
            previous_generator_profile_id=None,
            certification_statuses=None,
            routing_environment_class="production",
            approval_satisfied=False,
            expected_reason_code="HARD_GATE_APPROVAL_REQUIRED",
        )
    raise DdeError(
        "POLICY_DENIED",
        "unknown scenario class",
        retryable=False,
        details={
            "scenario_class": scenario_class,
            "known_real_classes": list(REAL_SCENARIO_CLASSES),
        },
    )


@dataclass(frozen=True)
class ScenarioRunResult:
    """One scenario's real `evaluate()` outcome, checked against the
    fixture's own stated expectation."""

    scenario_class: str
    workload_class: str
    selected_profile_id: str
    reason_codes: tuple[str, ...]
    expected_reason_code: str
    passed: bool

    def to_json(self) -> dict[str, object]:
        return {
            "scenario_class": self.scenario_class,
            "workload_class": self.workload_class,
            "selected_worker_profile_id": self.selected_profile_id,
            "reason_codes": list(self.reason_codes),
            "expected_reason_code": self.expected_reason_code,
            "passed": self.passed,
        }


def run_scenario(
    scenario_class: str, *, seed: str, tenant_id: UUID, project_id: UUID
) -> ScenarioRunResult:
    """Build the real fixture and run it through the real
    `engine.routing.rules.evaluate()` pipeline -- never
    `RouterService.route()`, so nothing here ever persists a production
    `RouteDecision`."""
    fixture = build_fixture(
        scenario_class, seed=seed, tenant_id=tenant_id, project_id=project_id
    )
    result: RoutingResult = evaluate(
        fixture.task,
        workload_class=fixture.workload_class,
        previous_generator_profile_id=fixture.previous_generator_profile_id,
        certification_statuses=fixture.certification_statuses,
        routing_environment_class=fixture.routing_environment_class,
        approval_satisfied=fixture.approval_satisfied,
    )
    passed = fixture.expected_reason_code in result.reason_codes
    return ScenarioRunResult(
        scenario_class=scenario_class,
        workload_class=result.workload_class,
        selected_profile_id=result.selected_profile_id,
        reason_codes=result.reason_codes,
        expected_reason_code=fixture.expected_reason_code,
        passed=passed,
    )


__all__ = [
    "DEFERRED_SCENARIO_CLASSES",
    "REAL_SCENARIO_CLASSES",
    "SCENARIO_GENERATOR_INDEPENDENCE_VIOLATION",
    "SCENARIO_HARD_GATE_APPROVAL_REQUIRED",
    "SCENARIO_WORKER_OUTAGE",
    "ScenarioFixture",
    "ScenarioRunResult",
    "build_fixture",
    "run_scenario",
]
