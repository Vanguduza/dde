# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class InstructionIR(BaseModel):
    """
    Canonical instruction delivery IR compiled from Project Truth, DDE policy and
    qualified guidance; emitted harness files are not truth.
    """

    model_config = ConfigDict(extra="forbid")

    version: str
    project_truth_hash: str
    policy_hash: str
    constraints: list[str]
    guidance: list[str]
    provenance_refs: list[str]
    content_hash: str
