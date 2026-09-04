# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FrontendLock(BaseModel):
    """
    DDE-069 functional lock over part of a project's frontend. Owned by
    engine.studio.locks (LockService is the sole writer). The lock iconography in the
    golden mockup is product semantics, not decoration: a locked element cannot be
    silently overwritten by drag/drop, chat, template import, source retrieval,
    `/design`, an autonomous agent or a refactor, because every one of those compiles to
    the same FrontendMutation and every FrontendMutation is checked against the
    effective lock set. `scope_key` is a PXG key; a lock covers that node and everything
    contained beneath it, so locking a screen locks its regions without needing a row
    per descendant.
    """

    model_config = ConfigDict(extra="forbid")

    lock_id: UUID
    tenant_id: UUID
    project_id: UUID
    lock_kind: Literal[
        "GLOBAL_DESIGN",
        "SCREEN",
        "SECTION",
        "COMPONENT",
        "STYLE",
        "STRUCTURE",
        "BEHAVIOUR",
        "CONTENT",
        "TOKEN",
    ]
    scope_key: str
    status: Literal["ACTIVE", "RELEASED"]
    reason: str
    created_by: UUID
    released_by: UUID | None = None
    released_at: datetime | None = None
    lock_version: int
    created_at: datetime
    updated_at: datetime
