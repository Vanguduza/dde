"""`WorkerProfileRegistry` — Chapter 8.4's Worker Manager responsibility to
register configurations and gate ("exposes **only certified profiles** to
routing... enforces health before allocation") worker profiles.

Chapter 8.5 (DDE-025): each registered adapter carries a `ProfileIdentity`
tuple whose hash is the certification key. Smoke pass stamps
`smoke_passed_hash`. A hash that does not match the last smoke pass is
`STALE`: selectable in `development`, refused with `PROFILE_STALE` in any
other environment class. Unregistered profiles remain `PROFILE_STALE`.

In-memory, not a persisted table: Chapter 3.3 does not assign a
`worker_profiles` table to this mission. A process restart forgets smoke
passes and must re-run the smoke tier.

**Why this is not a duplicate of `engine.routing.registry.PROFILES`.**
That module is the router's static capability/environment fact table.
This registry answers whether a real, health-checked `WorkerAdapter` may
be invoked right now, and whether its current `profile_hash` is smoke-current.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.core.errors import DdeError
from engine.workers.adapter import Registration, WorkerAdapter, WorkerHealth
from engine.workers.certification import (
    ProfileIdentity,
    profile_hash,
    selectable,
)
from engine.workers.smoke import identity_of


@dataclass(frozen=True)
class CertifiedProfile:
    registration: Registration
    health: WorkerHealth
    adapter: WorkerAdapter
    identity: ProfileIdentity
    profile_hash: str
    smoke_passed_hash: str | None

    @property
    def status(self) -> str:
        if self.smoke_passed_hash == self.profile_hash:
            return "CERTIFIED"
        return "STALE"


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
        identity = identity_of(adapter)
        digest = profile_hash(identity)
        prior = self._certified.get(registration.worker_profile_id)
        smoke_passed = prior.smoke_passed_hash if prior is not None else None
        certified = CertifiedProfile(
            registration=registration,
            health=health,
            adapter=adapter,
            identity=identity,
            profile_hash=digest,
            smoke_passed_hash=smoke_passed,
        )
        self._certified[registration.worker_profile_id] = certified
        return certified

    def record_smoke_pass(
        self, worker_profile_id: str, digest: str
    ) -> CertifiedProfile:
        current = self._certified.get(worker_profile_id)
        if current is None:
            raise DdeError(
                "PROFILE_STALE",
                "Cannot record a smoke pass for an unregistered profile",
                retryable=False,
                details={"worker_profile_id": worker_profile_id},
            )
        if current.profile_hash != digest:
            raise DdeError(
                "PROFILE_STALE",
                "Smoke pass hash does not match the registered profile_hash",
                retryable=False,
                details={
                    "worker_profile_id": worker_profile_id,
                    "registered_hash": current.profile_hash,
                    "smoke_hash": digest,
                },
            )
        updated = CertifiedProfile(
            registration=current.registration,
            health=current.health,
            adapter=current.adapter,
            identity=current.identity,
            profile_hash=current.profile_hash,
            smoke_passed_hash=digest,
        )
        self._certified[worker_profile_id] = updated
        return updated

    def get_certified_adapter(
        self,
        worker_profile_id: str,
        *,
        environment_class: str = "development",
    ) -> WorkerAdapter:
        """Chapter 8.4: "exposes **only certified profiles**". Unknown
        profiles and production-class STALE profiles are `PROFILE_STALE`
        (Chapter 15.5) — never silently substituted."""
        certified = self._certified.get(worker_profile_id)
        if certified is None:
            raise DdeError(
                "PROFILE_STALE",
                "Worker profile is not a certified, registered profile",
                details={"worker_profile_id": worker_profile_id},
            )
        if not selectable(certified.status, environment_class=environment_class):
            raise DdeError(
                "PROFILE_STALE",
                "Worker profile_hash changed and smoke certification has not passed",
                retryable=False,
                details={
                    "worker_profile_id": worker_profile_id,
                    "status": certified.status,
                    "environment_class": environment_class,
                    "profile_hash": certified.profile_hash,
                    "smoke_passed_hash": certified.smoke_passed_hash,
                },
            )
        return certified.adapter

    def status_for(self, worker_profile_id: str) -> str | None:
        found = self._certified.get(worker_profile_id)
        if found is None:
            return None
        return found.status

    def certification_snapshot(self) -> dict[str, str]:
        return {
            profile_id: record.status for profile_id, record in self._certified.items()
        }

    def list_certified_profiles(self) -> tuple[str, ...]:
        return tuple(sorted(self._certified))
