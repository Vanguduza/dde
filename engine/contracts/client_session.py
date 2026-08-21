# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ClientSession(BaseModel):
    """
    Gateway session identity for Chapter 15.1. Identifies a connected client, not a
    manufacturing mission; many sessions may observe one mission and vice versa, subject
    to authorization. tenant_id is derived from the authenticated principal, never from
    a client-supplied target id (Chapter 13.9). scopes are the principal's baseline
    scopes for its client_type (Chapter 14.2), enforced before any command reaches Core.
    Owned by engine.gateway.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    tenant_id: UUID
    principal_id: UUID
    client_type: str
    device_id: UUID | None = None
    protocol_version: str
    scopes: list[str]
    connected_at: datetime
    last_seen_at: datetime
    subscriptions: list[str]
    status: str
    created_at: datetime
    updated_at: datetime
