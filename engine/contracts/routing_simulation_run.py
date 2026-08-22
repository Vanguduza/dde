# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RoutingSimulationRun(BaseModel):
    """
    Chapter 6.4: the Routing Simulation Model, retained and repositioned as an
    evaluation/fixture-generation subsystem -- 'never a training source for a production
    policy and never an authority'. One row is written per regression/stress-testing
    invocation of `engine.simulation`, against a real, deterministic adversarial fixture
    generator (never a hand-parameterised probability model), driving the real
    `engine.routing.rules.evaluate()` pipeline the same way production routing does.
    `experience_origin` is fixed to `simulation` and `excluded_from_routing_learning` is
    fixed `true` on every row -- Chapter 6.4: 'excluded by construction from any dataset
    used to train or promote a production policy.' `seed`, `scenario_classes` and
    `model_version` are persisted for reproducibility, exactly as the chapter requires
    ('simulation seeds, parameter sets and model versions are persisted').
    `disclosed_gaps` names any requested `scenario_classes` this Stage 1 slice cannot
    generate a real fixture for (no fabricated elimination signal), never silently
    skipped. Owned by engine.simulation (Chapter 3.8).
    """

    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    tenant_id: UUID
    project_id: UUID
    seed: str
    policy_version: str
    model_version: str
    scenario_classes: list[str]
    scenario_results: list[dict[str, object]]
    experience_origin: Literal["simulation"]
    excluded_from_routing_learning: bool
    disclosed_gaps: list[str]
    created_at: datetime
    updated_at: datetime
