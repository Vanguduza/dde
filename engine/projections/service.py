"""Mission Control projection — read models over durable rows (Chapter 3.6,
15.4, 13.4, 16).

The projection is a pure read aggregation. It owns no tables, writes no rows,
and is never a second source of truth (AGENTS.md). The attention model and
autonomy-economics metrics mirror Chapter 13.4 and the governance writer
`ApprovalService.attention_budget` (DDE-026); `test_mission_control_postgres`
pins the two derivations together so a divergence is caught rather than
assumed away.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.mission_control import MissionControl
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.governance.repository import ApprovalRepository, AttentionItemRepository
from engine.governance.types import OPEN_APPROVAL_STATUSES
from engine.missions.repository import MissionsRepository
from engine.projections.repository import MissionControlRepository
from engine.truth.db import open_unit_of_work


class MissionControlService:
    """Builds the Chapter 15.4 operational projection for one mission."""

    def __init__(
        self,
        engine: AsyncEngine,
        missions: MissionsRepository | None = None,
        approvals: ApprovalRepository | None = None,
        attention: AttentionItemRepository | None = None,
        events: MissionControlRepository | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._missions = missions or MissionsRepository()
        self._approvals = approvals or ApprovalRepository()
        self._attention = attention or AttentionItemRepository()
        self._events = events or MissionControlRepository()
        self._clock = clock or SystemClock()

    async def project(
        self, *, tenant_id: UUID, project_id: UUID, mission_id: UUID
    ) -> MissionControl:
        """Aggregate one mission's durable rows into its projection.

        The reads run inside one tenant/project-scoped unit of work so the
        projection is fail-closed under row-level security (Chapter 3.2): a
        mission outside the caller's tenant yields no rows, never another
        tenant's data.
        """
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            mission = await self._missions.get_mission(uow.connection, mission_id)
            if mission is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "Unknown mission",
                    details={"mission_id": str(mission_id)},
                )
            tasks = await self._missions.list_tasks_for_mission(
                uow.connection, mission_id
            )
            approvals = await self._approvals.list_for_mission(
                uow.connection, mission_id
            )
            attention = await self._attention.list_for_mission(
                uow.connection, mission_id
            )
            last_event_at = await self._events.latest_event_cursor(
                uow.connection, mission_id
            )
            now = self._clock.now()

            task_counts: dict[str, int] = {}
            for task in tasks:
                task_counts[task.status] = task_counts.get(task.status, 0) + 1

            open_items = [item for item in attention if item.status == "OPEN"]
            attention_debt = sum(1 for item in open_items if item.sla_due_at <= now)
            approvals_by_type: dict[str, int] = {}
            for approval in approvals:
                approvals_by_type[approval.approval_type] = (
                    approvals_by_type.get(approval.approval_type, 0) + 1
                )

            return MissionControl(
                mission_id=mission.mission_id,
                tenant_id=mission.tenant_id,
                project_id=mission.project_id,
                slug=mission.slug,
                title=mission.title,
                status=mission.status,
                autonomy_ceiling=mission.autonomy_ceiling,
                lock_version=mission.lock_version,
                task_total=len(tasks),
                task_counts=task_counts,
                tasks_completed=task_counts.get("COMPLETED", 0),
                open_attention_items=len(open_items),
                attention_debt=attention_debt,
                human_minutes=sum(float(a.human_minutes) for a in approvals),
                approvals_per_mission=len(approvals),
                approvals_by_type=approvals_by_type,
                blocked_requests=sum(
                    1 for a in approvals if a.status in OPEN_APPROVAL_STATUSES
                ),
                standing_approval_usage=sum(
                    1 for a in approvals if a.standing_id is not None
                ),
                last_event_at=last_event_at,
                created_at=mission.created_at,
                updated_at=mission.updated_at,
            )
