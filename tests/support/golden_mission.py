"""Chapter 19.2 golden-mission identity for the Flight Lab.

Slug, title and requirement match §19.2 (`MISSION-ERP-000421` /
`REQ-AP-019`). The executable spine is the existing Stage-1
verification-terminated graph (mission → graph → task → context →
route → plan → environment → workspace → run → verify → integrate),
not a manufactured seven-node ERP product. S7 adds worker-outage and
policy-rollback scenarios on that identity.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.mission_trace_fixtures import (
    TraceableMission,
    build_traceable_mission,
)

GOLDEN_MISSION_SLUG = "MISSION-ERP-000421"
GOLDEN_MISSION_TITLE = "Implement supplier credit limits"
GOLDEN_MISSION_INTENT = (
    "Implement supplier credit limits as the Chapter 19.2 golden mission"
)
GOLDEN_REQUIREMENT_SLUG = "REQ-AP-019"
GOLDEN_REQUIREMENT_STATEMENT = "Supplier credit limits are enforced at posting time."
GOLDEN_WRITE_PATH = "engine/routing/golden-mission-erp.txt"


async def build_golden_mission(
    engine: AsyncEngine,
    root: Path,
) -> TraceableMission:
    """Full spine under the §19.2 identity, through real production services."""
    return await build_traceable_mission(
        engine,
        root,
        mission_slug=GOLDEN_MISSION_SLUG,
        mission_title=GOLDEN_MISSION_TITLE,
        mission_intent=GOLDEN_MISSION_INTENT,
        requirement_slug=GOLDEN_REQUIREMENT_SLUG,
        requirement_statement=GOLDEN_REQUIREMENT_STATEMENT,
        write_path=GOLDEN_WRITE_PATH,
    )


def golden_mission_branch(mission_id: UUID) -> str:
    return f"mission/{mission_id}"
