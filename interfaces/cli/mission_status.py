"""`dde mission status <mission_id>` -- a lighter-weight complement to
`dde mission trace` (DDE-014): a quick read of a mission's current
lifecycle state, its materialised Tasks grouped by status, and the
TaskGraph version(s) those tasks belong to -- without walking the full
ContextPackage / RouteDecision / ExecutionPlan / ExecutionEnvironment /
Workspace / WorkerRun / VerificationRun / Evidence / IntegrationProposal
spine `mission trace` reconstructs (and without `mission trace`'s Chapter
1 exit-gate check, which is specific to proving generator/verifier
independence, not a general "how's this mission doing" query).

Chapter 18's Day-1 walkthrough and the CLI/operations chapters name
`dde mission trace` explicitly but never name or specify a lighter status
command; this module is DDE-015's reasonable minimal design for that real,
missing gap.

**Boundary note.** Same posture as `interfaces.cli.mission_trace`: reads
`engine.missions`/`engine.planning` repositories directly under one shared,
RLS-scoped `PostgresUnitOfWork`, because Chapter 15's Gateway read
endpoints for missions do not exist yet either.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.mission import Mission
from engine.contracts.task import Task
from engine.contracts.task_graph import TaskGraph
from engine.core.errors import DdeError
from engine.missions.repository import MissionsRepository
from engine.planning.repository import TaskGraphRepository
from engine.truth.db import open_unit_of_work
from interfaces.cli.mission_trace import UNKNOWN_MISSION

#: Re-exported so `__main__` maps both `mission status` and `mission trace`
#: `UNKNOWN_MISSION` failures onto the same exit code without redefining
#: the error-code string in a second place.
__all__ = [
    "UNKNOWN_MISSION",
    "MissionStatus",
    "build_mission_status",
    "render_mission_status",
]


@dataclass(frozen=True)
class MissionStatus:
    mission: Mission
    tasks: list[Task]
    task_graphs: list[TaskGraph]


async def build_mission_status(
    engine: AsyncEngine,
    *,
    tenant_id: UUID,
    mission_id: UUID,
    project_id: UUID | None = None,
) -> MissionStatus:
    """Read a mission's real current state: its own row, every persisted
    `Task` for it, and every `TaskGraph` those tasks actually reference
    (deduplicated, since template-mode planning materialises exactly one
    graph per mission today but this command does not assume that will
    always hold). Raises `DdeError(UNKNOWN_MISSION, ...)` if no mission
    with this id is visible in the caller's tenant scope -- the same
    fail-closed RLS posture `mission_trace.build_mission_trace` uses."""
    missions = MissionsRepository()
    task_graphs_repo = TaskGraphRepository()

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
        graph_ids = {task.graph_id for task in tasks}
        graphs: list[TaskGraph] = []
        for graph_id in graph_ids:
            graph = await task_graphs_repo.get_task_graph(connection, graph_id)
            if graph is not None:
                graphs.append(graph)
        await uow.commit()

    graphs.sort(key=lambda graph: graph.version)
    return MissionStatus(mission=mission, tasks=tasks, task_graphs=graphs)


def render_mission_status(status: MissionStatus) -> str:
    """Plain, scriptable text -- consistent with `mission_trace`'s
    rendering style, but deliberately shorter: no per-node evidence walk,
    just the mission header, its TaskGraph(s), and a status histogram over
    its Tasks."""
    mission = status.mission
    lines = [
        "DDE Mission Status",
        "=" * 78,
        f"Mission {mission.mission_id}  slug={mission.slug!r}  status={mission.status}",
        f"  intent: {mission.intent}",
        f"  success_definition: {mission.success_definition}",
        f"  autonomy_ceiling: {mission.autonomy_ceiling}  "
        f"lock_version: {mission.lock_version}",
        "",
    ]

    if status.task_graphs:
        lines.append("TaskGraphs:")
        for graph in status.task_graphs:
            lines.append(
                f"  TaskGraph {graph.graph_id}  v{graph.version}  "
                f"status={graph.status}  mode={graph.planning_mode}"
            )
    else:
        lines.append("TaskGraphs: none recorded")
    lines.append("")

    counts = Counter(task.status for task in status.tasks)
    lines.append(f"Tasks: {len(status.tasks)} total")
    if counts:
        for task_status in sorted(counts):
            lines.append(f"  {task_status}: {counts[task_status]}")
    else:
        lines.append("  none recorded")

    return "\n".join(lines)
