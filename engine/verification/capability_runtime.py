"""Lease-enforced capability decorators for non-worker verification subjects.

The adapters behind these decorators remain ordinary provider/runtime adapters.
Authority comes from a real Chapter 9 CapabilityLease and is re-checked before
every capability call. WorkerRun-bound leases are deliberately rejected by
`CapabilityLeaseService.require_active_lease`, so this surface cannot bypass
worker kill-flag enforcement.
"""

from __future__ import annotations

from uuid import UUID

from engine.capabilities.browser import (
    BrowserCapability,
    BrowserCaptureResult,
    BrowserCaptureSpec,
    BrowserProbeResult,
    BrowserProbeSpec,
)
from engine.capabilities.lease_service import CapabilityLeaseService
from engine.capabilities.visual_critic import (
    VisualCriticCapability,
    VisualCritiqueRequest,
    VisualCritiqueResult,
)

CAPABILITY_BROWSER = "capability.browser"
CAPABILITY_VISUAL_CRITIQUE = "capability.visual_critique"


class LeaseBoundBrowserCapability:
    def __init__(
        self,
        *,
        leases: CapabilityLeaseService,
        tenant_id: UUID,
        project_id: UUID,
        lease_id: UUID,
        inner: BrowserCapability,
    ) -> None:
        self._leases = leases
        self._tenant_id = tenant_id
        self._project_id = project_id
        self._lease_id = lease_id
        self._inner = inner

    async def _require(self) -> None:
        await self._leases.require_active_lease(
            tenant_id=self._tenant_id,
            project_id=self._project_id,
            lease_id=self._lease_id,
            capability_id=CAPABILITY_BROWSER,
        )

    async def probe(self, spec: BrowserProbeSpec) -> BrowserProbeResult:
        await self._require()
        return await self._inner.probe(spec)

    async def screenshot(self, spec: BrowserCaptureSpec) -> BrowserCaptureResult:
        await self._require()
        return await self._inner.screenshot(spec)


class LeaseBoundVisualCriticCapability:
    def __init__(
        self,
        *,
        leases: CapabilityLeaseService,
        tenant_id: UUID,
        project_id: UUID,
        lease_id: UUID,
        inner: VisualCriticCapability,
    ) -> None:
        self._leases = leases
        self._tenant_id = tenant_id
        self._project_id = project_id
        self._lease_id = lease_id
        self._inner = inner

    async def critique(self, request: VisualCritiqueRequest) -> VisualCritiqueResult:
        await self._leases.require_active_lease(
            tenant_id=self._tenant_id,
            project_id=self._project_id,
            lease_id=self._lease_id,
            capability_id=CAPABILITY_VISUAL_CRITIQUE,
        )
        return await self._inner.critique(request)
