"""Shared PostgreSQL fixture for `engine.capabilities` (Chapter 19.1).

`ensure_capabilities_seeded` registers DDE-016's real Stage-1 capability
portfolio (`engine.capabilities.seed.seed_capabilities`) so that DDE-017's
`WorkerManagerService.invoke_run`/`WorkspaceService.snapshot` -- which now
require a real, granted `CapabilityLease` before performing their real side
effects -- have a real, `CERTIFIED`/`ACTIVE` `CapabilityDescriptor` to lease
against. `seed_capabilities` is itself idempotent (DDE-016), so this is safe
to call once per fixture tenant, not once globally.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.capabilities.seed import seed_capabilities
from engine.capabilities.service import CapabilityRegistryService


async def ensure_capabilities_seeded(
    engine: AsyncEngine, *, tenant_id: UUID, project_id: UUID
) -> None:
    await seed_capabilities(
        CapabilityRegistryService(engine),
        tenant_id=tenant_id,
        project_id=project_id,
    )
