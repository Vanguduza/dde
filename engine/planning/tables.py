"""SQLAlchemy Core tables for TaskGraph persistence (Chapter 3.8).

Hand-written to mirror `schemas/sql/0001_stage1.sql`, which is generated from
`schemas/objects/{task_graph,task_graph_edge}.json` — the schema is
authoritative (Chapter 3.1); this module only maps the same columns onto
SQLAlchemy Core so `engine.planning` can read and write them inside a shared
PostgreSQL transaction (Chapter 3.5).

Chapter 3.8's object ownership matrix lists `TaskGraph`'s owner module as
`planning`; this module (and `engine.planning.repository`/
`engine.planning.service`) is that production writer. `task_graph_edges`
carries the same ownership for the same reason: an edge only exists in the
context of the graph that contains it. This corrects the DDE-006 divergence
that had briefly consolidated both tables under `engine.missions` — see the
git history of `engine/missions/tables.py` for that flagged interim state.
`missions` and `tasks` remain owned by `engine.missions` (Chapter 3.8 assigns
`Task` to `missions`).
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Column, Integer, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

task_graphs = Table(
    "task_graphs",
    metadata,
    Column("graph_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("version", Integer, nullable=False),
    Column("supersedes_id", Uuid(as_uuid=True), nullable=True),
    Column("status", Text, nullable=False),
    Column("planning_mode", Text, nullable=False),
    Column("planner_policy_version", Text, nullable=False),
    Column("rationale", Text, nullable=False),
    Column("open_questions", JSONB, nullable=False),
    Column("graph_hash", Text, nullable=False),
    Column("created_by_principal", Uuid(as_uuid=True), nullable=False),
    Column("lock_version", Integer, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

task_graph_edges = Table(
    "task_graph_edges",
    metadata,
    Column("edge_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("graph_id", Uuid(as_uuid=True), nullable=False),
    Column("from_task_id", Uuid(as_uuid=True), nullable=False),
    Column("to_task_id", Uuid(as_uuid=True), nullable=False),
    Column("edge_type", Text, nullable=False),
    Column("contract_ref", Text, nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
