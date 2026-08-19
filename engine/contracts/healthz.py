# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Healthz(BaseModel):
    """Liveness response from Chapter 17.3."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
