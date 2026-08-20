"""`dde mission trace <mission_id>` -- Chapter 18's Day-1 walkthrough step 6
and Chapter 18.2's Stage 1 exit gate, read literally from Chapter 1:

    "The mission is only successful when `dde mission trace` shows an
    evidence record produced by a verification run that the generating
    worker did not control."

**What this module is, and is not.** DDE-012 already built `Evidence` as a
real, persisted, append-only, content-hashed object owned by
`engine.verification` (Chapter 11.7); `engine.verification.runner` already
records Chapter 11.4's generator/verifier independence fact on every
`Evidence` row via `independence_flags` (`generator_worker_profile_id`,
`verifier`, `independent`) -- and it holds *by construction*, not merely by
declaration: `VerificationRunnerService` never dispatches to a
`WorkerAdapter`/worker profile at all, so the worker profile that produced a
change never has a hand in judging it (see that module's docstring). This
mission therefore does **not** add a new Evidence concept, a new pipeline
stage, or a new independence *field* -- there is nothing missing to add.
What Chapter 1's sentence still requires, and what did not exist before this
mission, is a real command that walks the whole spine and makes that fact
*visible and independently re-checked* rather than merely trusted from a
stored boolean. `independence_proofs()` below is that check: it re-derives
independence from freshly-read `WorkerRun`/`VerificationRun`/`Evidence` rows
rather than trusting `Evidence.independence_flags["independent"]` at face
value.

Chapter 11.7 also asides that evidence-linked artifacts are "already in R2"
in the retention table (Chapter 3.7) -- that is `artifacts`' bytes storage
for a table this codebase's Stage 1 slice does not populate (no capability
yet writes `artifacts` rows); `evidence` itself is a metadata/hash row in
PostgreSQL, and DDE-012 already persists it there. Stage 1's real evidence
store is Postgres, full stop; adding R2/S3 object storage here would be
building Chapter 3.7's later-stage retention machinery for a table this
mission does not touch, which the mission brief explicitly rules out.

**Boundary note (see `interfaces/cli/__init__.py`'s docstring for the full
explanation):** this module reads `engine.*` repositories directly rather
than through Chapter 15's Gateway/API, because that API surface does not
exist yet for these objects. It calls only already-existing, read-only
repository methods (`get_*`/`list_*`) under one shared, RLS-scoped
`PostgresUnitOfWork` -- exactly the "composes sibling modules under one
shared unit of work" pattern every Stage 1 service already uses (Chapter
3.5) -- and never bypasses row-level security: every read requires a real
caller-supplied `tenant_id` to set `dde.tenant_id` before any query runs
(see `__main__.py`'s docstring for why `--tenant-id` is a required flag
rather than derived from the mission row itself).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.context.repository import ContextRepository
from engine.contracts.context_package import ContextPackage
from engine.contracts.evidence import Evidence
from engine.contracts.execution_environment import ExecutionEnvironment
from engine.contracts.execution_plan import ExecutionPlan
from engine.contracts.integration_proposal import IntegrationProposal
from engine.contracts.mission import Mission
from engine.contracts.route_decision import RouteDecision
from engine.contracts.task import Task
from engine.contracts.task_graph import TaskGraph
from engine.contracts.verification_run import VerificationRun
from engine.contracts.worker_run import WorkerRun
from engine.contracts.workspace import Workspace
from engine.contracts.write_scope_lease import WriteScopeLease
from engine.core.errors import DdeError
from engine.environments.repository import ExecutionEnvironmentRepository
from engine.execution.repository import ExecutionPlanRepository
from engine.integration.repository import (
    IntegrationProposalRepository,
    WriteScopeLeaseRepository,
)
from engine.missions.attempts import TaskAttemptRepository
from engine.missions.repository import MissionsRepository
from engine.planning.repository import TaskGraphRepository
from engine.routing.repository import RouteDecisionRepository
from engine.truth.db import open_unit_of_work
from engine.verification.repository import EvidenceRepository, VerificationRunRepository
from engine.workers.repository import WorkerRunRepository
from engine.workspaces.repository import WorkspaceRepository

#: Chapter 15.5-style typed error codes this command raises. Never a bare
#: `Exception` across the CLI/engine boundary (AGENTS.md style rule).
UNKNOWN_MISSION = "UNKNOWN_MISSION"
MISSION_TRACE_INCOMPLETE = "MISSION_TRACE_INCOMPLETE"

EXIT_OK = 0
EXIT_UNKNOWN_MISSION = 3
EXIT_INCOMPLETE = 4


@dataclass(frozen=True)
class ExecutionPlanTrace:
    plan: ExecutionPlan
    environment: ExecutionEnvironment | None
    write_scope_lease: WriteScopeLease | None


@dataclass(frozen=True)
class VerificationRunTrace:
    run: VerificationRun
    evidence: list[Evidence]


@dataclass(frozen=True)
class WorkerRunTrace:
    run: WorkerRun
    workspace: Workspace | None
    verification_runs: list[VerificationRunTrace]


@dataclass(frozen=True)
class TaskTrace:
    task: Task
    task_graph: TaskGraph | None
    context_packages: list[ContextPackage]
    route_decisions: list[RouteDecision]
    execution_plans: list[ExecutionPlanTrace]
    worker_runs: list[WorkerRunTrace]
    integration_proposals: list[IntegrationProposal]


@dataclass(frozen=True)
class MissionTrace:
    mission: Mission
    tasks: list[TaskTrace]


@dataclass(frozen=True)
class IndependenceProof:
    """Chapter 11.4's generator/verifier independence rule, re-derived from
    freshly-read rows rather than trusted from `Evidence.independence_flags`
    alone -- a real check this command performs, not an assertion by
    convention. `independent` is only ever `True` when every one of the
    following, independently fetched facts hold at once:

    - The evidence row's own `independent` flag says so.
    - Its claimed `generator_worker_profile_id` matches the *actual*
      `WorkerRun.worker_profile_id` this command just read.
    - Its claimed `verifier` is a non-empty identity that differs from that
      same worker profile (Chapter 11.4: "The worker profile that produced a
      change cannot execute the authoritative verification of that
      change").
    - The `VerificationRun`/`Evidence` rows this command fetched actually
      reference each other and the `WorkerRun` under test -- not merely
      three unrelated rows that happen to be readable.
    """

    task_id: UUID
    worker_run_id: UUID
    generator_worker_profile_id: str
    verification_run_id: UUID
    verifier_identity: str
    evidence_id: UUID
    content_hash: str
    independent: bool


async def build_mission_trace(
    engine: AsyncEngine,
    *,
    tenant_id: UUID,
    mission_id: UUID,
    project_id: UUID | None = None,
) -> MissionTrace:
    """Walk Chapter 3.9's real creation order end to end for one mission,
    reading only already-existing repository methods under one shared,
    RLS-scoped unit of work. Raises `DdeError(UNKNOWN_MISSION, ...)` if no
    mission with this id is visible in the caller's tenant scope; otherwise
    always returns a `MissionTrace`, even one with zero tasks -- callers
    that need "is this trace actually complete" decide that with
    `require_complete_trace`, so a caller can still print whatever was
    genuinely found before deciding whether it's enough."""
    missions = MissionsRepository()
    task_graphs = TaskGraphRepository()
    contexts = ContextRepository()
    routes = RouteDecisionRepository()
    plans_repo = ExecutionPlanRepository()
    environments_repo = ExecutionEnvironmentRepository()
    workspaces_repo = WorkspaceRepository()
    leases_repo = WriteScopeLeaseRepository()
    attempts_repo = TaskAttemptRepository()
    worker_runs_repo = WorkerRunRepository()
    verification_runs_repo = VerificationRunRepository()
    evidence_repo = EvidenceRepository()
    proposals_repo = IntegrationProposalRepository()

    async with open_unit_of_work(
        engine, tenant_id=tenant_id, project_id=project_id
    ) as uow:
        connection = uow.connection
        mission = await missions.get_mission(connection, mission_id)
        if mission is None:
            await uow.commit()
            raise DdeError(
                UNKNOWN_MISSION,
                "No mission with this id exists in the caller's tenant scope",
                details={"mission_id": str(mission_id), "tenant_id": str(tenant_id)},
            )

        tasks = await missions.list_tasks_for_mission(connection, mission_id)
        all_worker_runs = await worker_runs_repo.list_for_mission(
            connection, mission_id
        )
        all_proposals = await proposals_repo.list_for_mission(connection, mission_id)

        # `WorkerRun` carries `task_attempt_id`, not `task_id` (Chapter 3.9's
        # cardinality note: the Task<->WorkerRun link is carried through
        # TaskAttempt). Resolve each attempt once so runs can be grouped by
        # the task that actually owns them.
        attempt_task_ids: dict[UUID, UUID] = {}
        for run in all_worker_runs:
            if run.task_attempt_id in attempt_task_ids:
                continue
            attempt = await attempts_repo.get_attempt(connection, run.task_attempt_id)
            if attempt is not None:
                attempt_task_ids[run.task_attempt_id] = attempt.task_id

        graph_cache: dict[UUID, TaskGraph | None] = {}
        task_traces: list[TaskTrace] = []
        for task in tasks:
            if task.graph_id not in graph_cache:
                graph_cache[task.graph_id] = await task_graphs.get_task_graph(
                    connection, task.graph_id
                )

            context_packages = await contexts.list_versions_for_task(
                connection, task.task_id
            )
            route_decisions = await routes.list_for_task(connection, task.task_id)

            plan_traces: list[ExecutionPlanTrace] = []
            for plan in await plans_repo.list_for_task(connection, task.task_id):
                environment = await environments_repo.get_environment(
                    connection, plan.execution_environment_id
                )
                lease: WriteScopeLease | None = None
                if plan.write_scope_lease_id is not None:
                    lease = await leases_repo.get_lease(
                        connection, plan.write_scope_lease_id
                    )
                plan_traces.append(
                    ExecutionPlanTrace(
                        plan=plan, environment=environment, write_scope_lease=lease
                    )
                )

            worker_run_traces: list[WorkerRunTrace] = []
            for run in all_worker_runs:
                if attempt_task_ids.get(run.task_attempt_id) != task.task_id:
                    continue
                workspace = await workspaces_repo.get_workspace(
                    connection, run.workspace_id
                )
                verification_run_traces: list[VerificationRunTrace] = []
                for vrun in await verification_runs_repo.list_for_worker_run(
                    connection, run.run_id
                ):
                    evidence_rows = await evidence_repo.list_for_run(
                        connection, vrun.verification_run_id
                    )
                    verification_run_traces.append(
                        VerificationRunTrace(run=vrun, evidence=evidence_rows)
                    )
                worker_run_traces.append(
                    WorkerRunTrace(
                        run=run,
                        workspace=workspace,
                        verification_runs=verification_run_traces,
                    )
                )

            task_proposals = [
                proposal
                for proposal in all_proposals
                if proposal.task_id == task.task_id
            ]

            task_traces.append(
                TaskTrace(
                    task=task,
                    task_graph=graph_cache[task.graph_id],
                    context_packages=context_packages,
                    route_decisions=route_decisions,
                    execution_plans=plan_traces,
                    worker_runs=worker_run_traces,
                    integration_proposals=task_proposals,
                )
            )

        await uow.commit()

    return MissionTrace(mission=mission, tasks=task_traces)


def _check_independence(
    task_id: UUID,
    worker_run: WorkerRun,
    verification_run: VerificationRun,
    evidence: Evidence,
) -> IndependenceProof:
    flags = evidence.independence_flags
    generator = flags.get("generator_worker_profile_id")
    verifier = flags.get("verifier")
    independent = (
        bool(flags.get("independent"))
        and generator == worker_run.worker_profile_id
        and isinstance(verifier, str)
        and bool(verifier)
        and verifier != worker_run.worker_profile_id
        and evidence.verification_run_id == verification_run.verification_run_id
        and verification_run.worker_run_id == worker_run.run_id
    )
    return IndependenceProof(
        task_id=task_id,
        worker_run_id=worker_run.run_id,
        generator_worker_profile_id=worker_run.worker_profile_id,
        verification_run_id=verification_run.verification_run_id,
        verifier_identity=str(verifier) if verifier is not None else "unknown",
        evidence_id=evidence.evidence_id,
        content_hash=evidence.content_hash,
        independent=independent,
    )


def independence_proofs(trace: MissionTrace) -> list[IndependenceProof]:
    """Chapter 1's exit-gate sentence, made checkable: one `IndependenceProof`
    per `Evidence` row anywhere in the trace, each independently re-derived
    from the real `WorkerRun`/`VerificationRun`/`Evidence` rows this command
    fetched -- never a pass-through of the stored `independent` flag alone."""
    proofs: list[IndependenceProof] = []
    for task_trace in trace.tasks:
        for worker_run_trace in task_trace.worker_runs:
            for verification_trace in worker_run_trace.verification_runs:
                for evidence in verification_trace.evidence:
                    proofs.append(
                        _check_independence(
                            task_trace.task.task_id,
                            worker_run_trace.run,
                            verification_trace.run,
                            evidence,
                        )
                    )
    return proofs


def require_complete_trace(
    trace: MissionTrace, proofs: list[IndependenceProof]
) -> None:
    """Chapter 18.2's S1 exit gate needs more than "a mission row exists":
    it needs the whole spine reconstructed and Chapter 1's independence
    sentence actually proven. Raises a typed `DdeError` -- never lets a
    caller believe an incomplete trace is a finished one -- but only after
    the caller has already had the chance to print whatever was found."""
    if not trace.tasks:
        raise DdeError(
            MISSION_TRACE_INCOMPLETE,
            "Mission has no materialised tasks; nothing to trace",
            details={"mission_id": str(trace.mission.mission_id)},
        )
    if not any(proof.independent for proof in proofs):
        raise DdeError(
            MISSION_TRACE_INCOMPLETE,
            "No task in this mission has produced independently-verified "
            "evidence yet -- Chapter 1's exit-gate sentence is not proven",
            details={
                "mission_id": str(trace.mission.mission_id),
                "task_count": len(trace.tasks),
                "evidence_count": len(proofs),
            },
        )


def render_mission_trace(trace: MissionTrace, proofs: list[IndependenceProof]) -> str:
    """A plain, human-readable rendering of the real data model -- Chapter
    18's Day-1 walkthrough and the CLI/operations chapters name `dde mission
    trace` but never specify an exact output format, so this is the minimal
    reasonable shape: one section per spine node Chapter 3.9 defines, in
    creation order, ending with the literal proof Chapter 1 asks for."""
    lines: list[str] = []
    mission = trace.mission
    lines.append("DDE Mission Trace")
    lines.append("=" * 78)
    lines.append(
        f"Mission {mission.mission_id}  slug={mission.slug!r}  status={mission.status}"
    )
    lines.append(f"  intent: {mission.intent}")
    lines.append(f"  success_definition: {mission.success_definition}")
    lines.append("")

    proofs_by_evidence = {proof.evidence_id: proof for proof in proofs}

    for task_trace in trace.tasks:
        task = task_trace.task
        lines.append(
            f'Task {task.task_id}  "{task.title}"  status={task.status}  '
            f"class={task.task_class}"
        )
        graph = task_trace.task_graph
        if graph is not None:
            lines.append(
                f"  TaskGraph {graph.graph_id}  v{graph.version}  "
                f"status={graph.status}  mode={graph.planning_mode}"
            )
        else:
            lines.append("  TaskGraph: MISSING")

        if task_trace.context_packages:
            for context_package in task_trace.context_packages:
                lines.append(
                    f"  ContextPackage {context_package.package_id}  "
                    f"v{context_package.version}  status={context_package.status}  "
                    f"assembly_hash={context_package.assembly_hash}"
                )
        else:
            lines.append("  ContextPackage: none recorded")

        if task_trace.route_decisions:
            for route_decision in task_trace.route_decisions:
                lines.append(
                    f"  RouteDecision {route_decision.decision_id}  "
                    "selected_worker_profile_id="
                    f"{route_decision.selected_worker_profile_id}  "
                    f"source={route_decision.selection_source}"
                )
        else:
            lines.append("  RouteDecision: none recorded")

        if task_trace.execution_plans:
            for plan_trace in task_trace.execution_plans:
                plan = plan_trace.plan
                lines.append(
                    f"  ExecutionPlan {plan.plan_id}  "
                    f"worker_profile_id={plan.worker_profile_id}  "
                    f"status={plan.status}  autonomy_level={plan.autonomy_level}"
                )
                if plan_trace.environment is not None:
                    environment = plan_trace.environment
                    lines.append(
                        f"    ExecutionEnvironment {environment.environment_id}  "
                        f"class={environment.class_}  type={environment.type}  "
                        f"status={environment.status}"
                    )
                else:
                    lines.append("    ExecutionEnvironment: none recorded")
                if plan_trace.write_scope_lease is not None:
                    lease = plan_trace.write_scope_lease
                    lines.append(
                        f"    WriteScopeLease {lease.lease_id}  "
                        f"status={lease.status}  scope={lease.scope_patterns}"
                    )
        else:
            lines.append("  ExecutionPlan: none recorded")

        if task_trace.worker_runs:
            for worker_run_trace in task_trace.worker_runs:
                run = worker_run_trace.run
                lines.append(
                    f"  WorkerRun (GENERATOR) {run.run_id}  "
                    f"worker_profile_id={run.worker_profile_id}  "
                    f"status={run.status}"
                )
                if worker_run_trace.workspace is not None:
                    workspace = worker_run_trace.workspace
                    revision = workspace.current_revision or workspace.base_revision
                    lines.append(
                        f"    Workspace {workspace.workspace_id}  "
                        f"status={workspace.status}  revision={revision}"
                    )
                else:
                    lines.append("    Workspace: none recorded")

                if worker_run_trace.verification_runs:
                    for verification_trace in worker_run_trace.verification_runs:
                        vrun = verification_trace.run
                        lines.append(
                            "    VerificationRun (VERIFIER) "
                            f"{vrun.verification_run_id}  status={vrun.status}  "
                            f"confidence={vrun.confidence:.2f}"
                        )
                        if verification_trace.evidence:
                            for evidence in verification_trace.evidence:
                                proof = proofs_by_evidence.get(evidence.evidence_id)
                                verdict = (
                                    "INDEPENDENT"
                                    if proof is not None and proof.independent
                                    else "NOT PROVEN INDEPENDENT"
                                )
                                lines.append(
                                    f"      Evidence {evidence.evidence_id}  "
                                    f"content_hash={evidence.content_hash}  "
                                    f"produced_by={evidence.produced_by}  "
                                    f"status={evidence.status}"
                                )
                                lines.append(
                                    f"        independence: generator="
                                    f"{run.worker_profile_id}  verifier="
                                    f"{evidence.independence_flags.get('verifier')}"
                                    f"  -> {verdict}"
                                )
                        else:
                            lines.append("      Evidence: none recorded")
                else:
                    lines.append("    VerificationRun: none recorded")
        else:
            lines.append("  WorkerRun: none recorded")

        if task_trace.integration_proposals:
            for proposal in task_trace.integration_proposals:
                lines.append(
                    f"  IntegrationProposal {proposal.proposal_id}  "
                    f"status={proposal.status}  revision={proposal.proposed_revision}"
                )
        else:
            lines.append("  IntegrationProposal: none recorded")

        lines.append("")

    independent_count = sum(1 for proof in proofs if proof.independent)
    lines.append("-" * 78)
    lines.append(
        f"Summary: {len(trace.tasks)} task(s), {len(proofs)} evidence record(s), "
        f"{independent_count} with proven generator != verifier independence."
    )
    if independent_count > 0:
        lines.append(
            "Chapter 1 acceptance sentence: PROVEN -- at least one evidence "
            "record was produced by a verification run the generating worker "
            "did not control."
        )
    else:
        lines.append(
            "Chapter 1 acceptance sentence: NOT YET PROVEN -- no evidence "
            "record with confirmed generator/verifier independence exists "
            "for this mission."
        )
    return "\n".join(lines)


def trace_exit_code(trace: MissionTrace, proofs: list[IndependenceProof]) -> int:
    """Pure classification of an already-built trace, kept separate from
    `require_complete_trace` so a caller can compute an exit code without
    also choosing to raise."""
    if not trace.tasks:
        return EXIT_INCOMPLETE
    if not any(proof.independent for proof in proofs):
        return EXIT_INCOMPLETE
    return EXIT_OK
