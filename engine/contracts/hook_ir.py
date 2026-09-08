# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HookIR(BaseModel):
    """Harness-neutral executable hook policy with explicit scopes and evidence."""

    model_config = ConfigDict(extra="forbid")

    hook_id: str
    hook_class: str
    event: str
    matcher: dict[str, object]
    command: list[str] | None = None
    capability_id: str | None = None
    filesystem_scopes: list[str]
    network_scopes: list[str]
    secret_scopes: list[str]
    timeout_seconds: int
    failure_policy: Literal["BLOCK", "WARN", "ESCALATE"]
    evidence_types: list[str]
