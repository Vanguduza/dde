"""Chapter 8.5 tiered certification (DDE-025).

A profile is `model × harness × toolset × environment`. `profile_hash` is
the identity of that tuple. Smoke/Standard/Full are the only legal tiers.
A hash change whose smoke tier has not passed is `STALE`: visible to
operators, selectable in `development`, and not selectable by production
routing (Chapter 8.5).

No `worker_profiles` table exists in Chapter 3.3's assigned Stage 1/2/3
set (it is a global registry, like `policies`). Certification records are
therefore process-local on `WorkerProfileRegistry` and must be
re-established after a restart — they are not a second source of mission
state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from engine.core.hashing import canonical_json, sha256_hex

CertificationTier = Literal["smoke", "standard", "full"]
CertificationStatus = Literal["CERTIFIED", "STALE"]

SMOKE_MAX_SECONDS: Final = 15 * 60
SMOKE_MAX_USD: Final = 5.0
STANDARD_MAX_SECONDS: Final = 2 * 60 * 60

STALE_SELECTABLE_ENVIRONMENT_CLASSES: Final[frozenset[str]] = frozenset({"development"})

SMOKE_FIXTURE_IDS: Final[tuple[str, ...]] = (
    "tool_call_correctness",
    "structured_output",
    "file_write_safety",
    "workspace_containment",
    "cancellation",
    "checkpoint_resume",
    "cost_reporting_accuracy",
    "register_identity",
    "health_reports_status",
    "capabilities_declared",
    "terminate_cleanup",
    "profile_hash_stability",
)


@dataclass(frozen=True)
class ProfileIdentity:
    """Chapter 8.5's four-part profile tuple."""

    model_version: str
    harness_version: str
    toolset_manifest: str
    image_digest: str


def profile_hash(identity: ProfileIdentity) -> str:
    return sha256_hex(
        canonical_json(
            {
                "model_version": identity.model_version,
                "harness_version": identity.harness_version,
                "toolset_manifest": identity.toolset_manifest,
                "image_digest": identity.image_digest,
            }
        )
    )


def allow_stale(environment_class: str) -> bool:
    return environment_class in STALE_SELECTABLE_ENVIRONMENT_CLASSES


def selectable(status: str, *, environment_class: str) -> bool:
    if status == "CERTIFIED":
        return True
    if status == "STALE":
        return allow_stale(environment_class)
    return False
