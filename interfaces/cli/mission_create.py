"""`dde mission create` -- Chapter 1's Day-1 walkthrough only ever shows
`dde mission run "<intent>"` (Step 6), a single command that is supposed to
produce the *entire* spine (Mission -> TaskGraph -> ... -> Evidence ->
merged commit) from one free-text intent string. That command has no real
home yet: Chapter 2.6 is explicit that "Mission Kernel owns mission and
task state. It does not execute tools," and no later chapter names a
component whose job is "drive context compile -> route -> plan ->
provision -> worker run -> verify -> integrate for a whole mission
automatically" -- Chapter 18.3 places `TaskAttempt durability + replay`
and `failure taxonomy + recovery matrix + replan` at S3 (`DDE-023`,
`DDE-024`), which is the first point in the staged plan where a durable,
retryable execution-driving loop is chartered at all. Building that
orchestration now, ahead of its owning mission, would mean either faking
the missing steps or duplicating logic `tests/support/mission_trace_fixtures.
py` already shows requires composing ten-plus real services (execution
environment, workspace, git branches, worker adapter, verification runner,
integration queue) by hand. This module therefore does not implement
`mission run`; it implements the smallest *real* slice of Chapter 1's
walkthrough that has an unambiguous, already-built owner: creating the
Mission row itself, via the production `engine.missions.service.
MissionService` -- the sole writer of `missions` (Chapter 3.8) -- never by
inserting a row directly.

**Boundary note.** As with `interfaces.cli.mission_trace`, this reads/writes
`engine.*` services directly rather than through Chapter 15's Gateway/API,
because no Gateway mission-write endpoint exists yet either.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.mission import Mission
from engine.events.service import EventService
from engine.missions.service import MissionService


async def create_mission(
    engine: AsyncEngine,
    *,
    tenant_id: UUID,
    project_id: UUID,
    slug: str,
    title: str,
    intent: str,
    success_definition: str,
    scope: list[str],
    requirement_refs: list[str],
    autonomy_ceiling: int,
) -> Mission:
    """Persist a real, durable `Mission` row through `MissionService.
    create_mission` -- the same production write path every prior mission's
    tests already exercise -- so a caller can immediately re-read this
    mission from a fresh process (`mission status`, `mission trace`, a
    second `dde` invocation). Raises `DdeError("VERSION_CONFLICT", ...)`
    when `slug` is already used within this project; `MissionService`
    itself enforces that a slug is project-unique and immutable
    (Chapter 3.5), this module adds no additional validation of its own."""
    service = MissionService(engine, EventService(engine))
    return await service.create_mission(
        tenant_id=tenant_id,
        project_id=project_id,
        slug=slug,
        title=title,
        intent=intent,
        success_definition=success_definition,
        scope=scope,
        requirement_refs=requirement_refs,
        autonomy_ceiling=autonomy_ceiling,
    )


def render_created_mission(mission: Mission) -> str:
    """Plain, scriptable text -- consistent with `mission_trace`'s
    rendering style. No exact output format is specified anywhere in the
    blueprint for this command, since the blueprint never names it; this is
    DDE-015's minimal reasonable shape."""
    lines = [
        "Mission created",
        "=" * 78,
        f"mission_id: {mission.mission_id}",
        f"tenant_id: {mission.tenant_id}",
        f"project_id: {mission.project_id}",
        f"slug: {mission.slug!r}",
        f"title: {mission.title}",
        f"intent: {mission.intent}",
        f"success_definition: {mission.success_definition}",
        f"scope: {mission.scope}",
        f"requirement_refs: {mission.requirement_refs}",
        f"status: {mission.status}",
        f"autonomy_ceiling: {mission.autonomy_ceiling}",
        f"lock_version: {mission.lock_version}",
    ]
    return "\n".join(lines)
