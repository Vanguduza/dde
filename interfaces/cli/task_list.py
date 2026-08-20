"""`dde task list <mission_id>` -- lists every real, persisted `Task` row
for a mission (Chapter 3.8's `tasks` table, owned by `engine.missions`).

Chapter 18's Day-1 walkthrough and the CLI/operations chapters never name a
dedicated task-listing command; this module is DDE-015's minimal, real
complement to `mission status`/`mission trace` for inspecting a mission's
task set on its own, without a full spine walk.

**Boundary note.** Same posture as `interfaces.cli.mission_trace` /
`interfaces.cli.mission_status`: reads `engine.missions.MissionsRepository`
directly under one shared, RLS-scoped `PostgresUnitOfWork`, because
Chapter 15's Gateway read endpoints for tasks do not exist yet either.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.mission import Mission
from engine.contracts.task import Task
from engine.core.errors import DdeError
from engine.missions.repository import MissionsRepository
from engine.truth.db import open_unit_of_work
from interfaces.cli.mission_trace import UNKNOWN_MISSION

__all__ = [
    "UNKNOWN_MISSION",
    "TaskListing",
    "build_task_listing",
    "render_task_listing",
]


@dataclass(frozen=True)
class TaskListing:
    mission: Mission
    tasks: list[Task]


async def build_task_listing(
    engine: AsyncEngine,
    *,
    tenant_id: UUID,
    mission_id: UUID,
    project_id: UUID | None = None,
) -> TaskListing:
    """Verify the mission is real and visible in the caller's tenant scope
    before listing its tasks -- a syntactically valid but never-created
    `mission_id` must be a clear, typed `UNKNOWN_MISSION` failure (Chapter
    19.1's negative-test category), never an empty-but-successful listing
    that looks identical to "this mission genuinely has zero tasks yet"."""
    missions = MissionsRepository()

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
        await uow.commit()

    return TaskListing(mission=mission, tasks=tasks)


def render_task_listing(listing: TaskListing) -> str:
    """Plain, scriptable text: one line per task, in the same creation
    order `MissionsRepository.list_tasks_for_mission` already returns."""
    lines = [
        f"Tasks for mission {listing.mission.mission_id} "
        f"(slug={listing.mission.slug!r})",
        "=" * 78,
    ]
    if not listing.tasks:
        lines.append("No tasks recorded for this mission yet.")
        return "\n".join(lines)

    for task in listing.tasks:
        lines.append(
            f"Task {task.task_id}  status={task.status}  "
            f"class={task.task_class}  title={task.title!r}"
        )
    lines.append("")
    lines.append(f"Total: {len(listing.tasks)} task(s)")
    return "\n".join(lines)
