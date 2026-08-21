"""`LocalImplementationAdapter` — DDE-025's second WorkerAdapter.

T1, DDE-native, ActionBindable. Backs `profile.longcontext_economy` so
bulk-implementation routing has a real certified generator distinct from
the verification runner (Chapter 11.4 independence). Same workspace
execute/write/snapshot path as `ScriptedWorkerAdapter` because that is the
honest local-process substrate; the profile tuple differs (`harness_version`)
so a hash change is observable.
"""

from __future__ import annotations

from engine.capabilities.lease_service import CapabilityLeaseService
from engine.routing.policy import PROFILE_LONGCONTEXT_ECONOMY
from engine.workers.certification import ProfileIdentity
from engine.workers.scripted_adapter import ScriptedWorkerAdapter
from engine.workspaces.service import WorkspaceService

IMPLEMENTATION_WORKER_ID = "worker.local-implementation-v1"
IMPLEMENTATION_IDENTITY = ProfileIdentity(
    model_version="none",
    harness_version="local-implementation-v1",
    toolset_manifest="workspace.execute+write+snapshot",
    image_digest="local-process",
)


class LocalImplementationAdapter(ScriptedWorkerAdapter):
    """Chapter 8.1 contract behind `profile.longcontext_economy`."""

    def __init__(
        self, workspaces: WorkspaceService, leases: CapabilityLeaseService
    ) -> None:
        super().__init__(
            workspaces,
            leases,
            worker_id=IMPLEMENTATION_WORKER_ID,
            worker_profile_id=PROFILE_LONGCONTEXT_ECONOMY,
            identity=IMPLEMENTATION_IDENTITY,
        )
