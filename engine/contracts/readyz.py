# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Readyz(BaseModel):
    """Readiness response from Chapter 17.3."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "not_ready"]
    database: bool
    redis: bool
    migrations: Literal["head", "behind", "unknown"]
