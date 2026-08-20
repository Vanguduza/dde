"""`WorkerProfileRegistry` — Chapter 8.4's Worker Manager responsibility to
register("Registers configurations") and gate ("exposes **only certified
profiles** to routing... enforces health before allocation") worker
profiles. In-memory, not a persisted table: Chapter 3.3 does not assign a
`worker_profiles` table to any Stage 1 mission (the same reason
`engine.routing.registry` gives for its own constant, in-code profile
table), and this mission's brief scopes "one real certified profile" —
Chapter 8.5's tiered Smoke/Standard/Full certification suite (weekly
re-certs, chaos, cost ceilings) is explicitly deferred (S3/DDE-025:
"second and third worker adapters + tiered certification").

**Why this is not a duplicate of `engine.routing.registry.PROFILES`.**
That module is an explicitly-flagged Stage 1 stand-in the *router* uses,
before any plan or run exists, to answer "which capabilities/environment
classes does profile X claim" for Chapter 6.1's gates 1 and 4 — a static,
declarative fact table with no notion of liveness or certification. This
registry answers a different, later question: "is there a real, registered,
health-checked `WorkerAdapter` instance behind profile X that the Worker
Manager may actually invoke right now" — Chapter 8.4's "enforces health
before allocation." A profile can appear in `engine.routing.registry`
(eligible to be *selected*) while being entirely absent or `STALE` here
(not eligible to be *run*) — which is exactly Chapter 8.5's point: "the
failure mode is a blocked route, not a silent bypass." Neither module can
replace the other without conflating those two questions; this mission does
not touch `engine.routing.registry` (out of this mission's constraint
against refactoring `engine.routing`).

Full `profile_hash`/smoke-tier `STALE` tracking (Chapter 8.5) is not
implemented; the minimal, real analogue kept here is narrower but genuine:
a profile is certified only once `register()` succeeds and `health()`
reports healthy, and `get_certified_adapter` raises the chapter's own
`PROFILE_STALE` error code (Chapter 15.5) for anything not certified —
never silently substituting or bypassing.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.core.errors import DdeError
from engine.workers.adapter import Registration, WorkerAdapter, WorkerHealth


@dataclass(frozen=True)
class CertifiedProfile:
    registration: Registration
    health: WorkerHealth
    adapter: WorkerAdapter


class WorkerProfileRegistry:
    """Chapter 8.4's registration/certification surface. `register_profile`
    is synchronous bookkeeping over an async health check — call it once at
    process/service wiring time, not per run."""

    def __init__(self) -> None:
        self._certified: dict[str, CertifiedProfile] = {}

    async def register_profile(self, adapter: WorkerAdapter) -> CertifiedProfile:
        registration = await adapter.register()
        health = await adapter.health()
        if not health.healthy:
            raise DdeError(
                "WORKER_UNAVAILABLE",
                "Worker adapter failed its health check at registration",
                details={
                    "worker_id": registration.worker_id,
                    "worker_profile_id": registration.worker_profile_id,
                    "detail": health.detail,
                },
            )
        certified = CertifiedProfile(
            registration=registration, health=health, adapter=adapter
        )
        self._certified[registration.worker_profile_id] = certified
        return certified

    def get_certified_adapter(self, worker_profile_id: str) -> WorkerAdapter:
        """Chapter 8.4: "exposes **only certified profiles**". An unknown or
        never-registered profile is `PROFILE_STALE` (Chapter 15.5's real
        error code for "not currently selectable") rather than a generic
        lookup failure."""
        certified = self._certified.get(worker_profile_id)
        if certified is None:
            raise DdeError(
                "PROFILE_STALE",
                "Worker profile is not a certified, registered profile",
                details={"worker_profile_id": worker_profile_id},
            )
        return certified.adapter

    def list_certified_profiles(self) -> tuple[str, ...]:
        return tuple(sorted(self._certified))
