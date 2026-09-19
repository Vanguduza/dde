# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BrowserCapabilitySession(BaseModel):
    """
    EDR-0019 Epic K governed browser session. The capability ladder runs L0_FETCH_ONLY
    -> L1_DETERMINISTIC_BROWSER -> L2_STRUCTURED_EXTRACTION ->
    L3_SEMANTIC_ELEMENT_RESOLUTION -> L4_BOUNDED_DISCOVERY (owner/policy gated) ->
    L5_AGENTIC_BROWSER (off by default). Semantic output is never verification
    authority: release, accessibility, pixel and security verification remain
    independent DDE verifier duties. Browser profiles are secrets -- profiles are
    isolated per project/provider, raw cookies are never model-visible, never logged and
    never exported into prompts, and every session is leased, expiring and revocable.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    task_id: UUID | None = None
    capability_level: Literal[
        "L0_FETCH_ONLY",
        "L1_DETERMINISTIC_BROWSER",
        "L2_STRUCTURED_EXTRACTION",
        "L3_SEMANTIC_ELEMENT_RESOLUTION",
        "L4_BOUNDED_DISCOVERY",
        "L5_AGENTIC_BROWSER",
    ]
    profile_ref: str
    profile_isolated: bool
    capability_lease_id: UUID | None = None
    allowed_domains: list[str]
    semantic_layer_used: bool
    verification_authority: Literal["NONE"]
    screenshot_redaction: bool
    cookie_export_blocked: bool
    state: Literal["REQUESTED", "ACTIVE", "CLOSED", "EXPIRED", "REVOKED", "REFUSED"]
    refusal_reason: str | None = None
    issued_at: datetime
    expires_at: datetime
    closed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
