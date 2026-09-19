# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DiscoveryTrial(BaseModel):
    """
    EDR-0019 Epic C ExecutableTrialManifest: a bounded sandbox trial of a discovery
    candidate. A passing trial advances lifecycle_state to SANDBOX_TESTED and never
    raises source_trust or grants execution authority in production. Trials run under
    the ordinary CapabilityLease/sandbox law with no DDE credentials and no network
    beyond the declared scopes.
    """

    model_config = ConfigDict(extra="forbid")

    trial_id: UUID
    tenant_id: UUID
    project_id: UUID
    candidate_id: UUID
    trial_kind: Literal[
        "STATIC_ONLY",
        "IMPORT_SMOKE",
        "COMMAND_SMOKE",
        "FIXTURE_REPLAY",
    ]
    sandbox_profile: str
    declared_network_scopes: list[str]
    declared_filesystem_scopes: list[str]
    capability_lease_id: UUID | None = None
    command: list[str]
    input_digest: str | None = None
    outcome: Literal["PENDING", "PASSED", "FAILED", "REFUSED", "TIMEOUT", "ERROR"]
    observed_signals: list[dict[str, object]]
    evidence_pointer: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
