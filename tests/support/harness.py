"""In-memory engines wired the way Core modules share one unit of work.

`GovernanceRecords` (Chapter 13.3.5) is deliberately not part of this
harness: it is a PostgreSQL-backed composition of `TruthService` and
`AuditService` (Chapter 3.5 cross-module transaction), so it is exercised
against a real database in `tests/unit/test_governance.py` and
`tests/recovery/test_governance_recovery.py` via `tests/support/db.py`
instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from engine.audit.ledger import AuditLedger, AuditStore
from engine.core.clock import SystemClock
from engine.core.ids import uuid7
from engine.events.engine import EventEngine, EventStore
from engine.missions.kernel import MissionKernel, MissionStore
from engine.planning.planner import TaskPlanner
from engine.truth.engine import TruthEngine, TruthStore


@dataclass
class Harness:
    tenant_id: UUID
    project_id: UUID
    principal_id: UUID
    truth: TruthEngine
    truth_store: TruthStore
    events: EventEngine
    event_store: EventStore
    audit: AuditLedger
    missions: MissionKernel
    mission_store: MissionStore
    planner: TaskPlanner


def build_harness() -> Harness:
    clock = SystemClock()
    truth_store = TruthStore()
    event_store = EventStore()
    mission_store = MissionStore()
    events = EventEngine(event_store, clock)
    truth = TruthEngine(truth_store, clock)
    audit = AuditLedger(AuditStore(), clock)
    missions = MissionKernel(mission_store, events, clock)
    planner = TaskPlanner(missions, mission_store, clock)
    return Harness(
        tenant_id=uuid7(),
        project_id=uuid7(),
        principal_id=uuid7(),
        truth=truth,
        truth_store=truth_store,
        events=events,
        event_store=event_store,
        audit=audit,
        missions=missions,
        mission_store=mission_store,
        planner=planner,
    )


CONSTITUTION = """# Product Constitution

## Purpose
Control plane for software manufacturing.

## Target users
Engineering organisations.

## Non-negotiable constraints
Project Truth outranks agent memory.

## Core workflows
Mission to verified evidence.

## UX principles
Attention is scarce.

## Security principles
No ambient credentials.

## Architecture principles
One schema source of truth.

## Explicit exclusions
No agent framework for core state.

## Governance rules
Accepted EDRs are superseded, never rewritten.
"""
