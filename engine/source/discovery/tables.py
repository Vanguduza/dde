"""SQLAlchemy Core mappings for EDR-0019 discovery.

Column sets mirror `schemas/objects/discovery_*.json`; the contract test
`test_discovery_tables_match_the_generated_schema` fails if they drift.
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Boolean, Column, Integer, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

from engine.studio.tables import metadata

discovery_candidates = Table(
    "discovery_candidates",
    metadata,
    Column("candidate_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("canonical_locator", Text, nullable=False),
    Column("normalized_identity_key", Text, nullable=False),
    Column("identity_scheme", Text, nullable=False),
    Column("title", Text),
    Column("publisher", Text),
    Column("lifecycle_state", Text, nullable=False),
    Column("source_trust", Text, nullable=False),
    Column("discovered_by", Text, nullable=False),
    Column("discovery_refs", JSONB, nullable=False),
    Column("observation_count", Integer, nullable=False),
    Column("source_id", Uuid(as_uuid=True)),
    Column("admitted_resource_id", Uuid(as_uuid=True)),
    Column("supersedes_candidate_id", Uuid(as_uuid=True)),
    Column("license_ids", JSONB, nullable=False),
    Column("content_hash", Text),
    Column("sanitizer_findings", JSONB, nullable=False),
    Column("architecture_findings", JSONB, nullable=False),
    Column("first_seen_at", TIMESTAMP(timezone=True), nullable=False),
    Column("last_observed_at", TIMESTAMP(timezone=True), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

discovery_transitions = Table(
    "discovery_transitions",
    metadata,
    Column("transition_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("candidate_id", Uuid(as_uuid=True), nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("from_state", Text),
    Column("to_state", Text, nullable=False),
    Column("reason_code", Text, nullable=False),
    Column("actor", Text, nullable=False),
    Column("evidence_pointer", Text),
    Column("decision_hash", Text, nullable=False),
    Column("occurred_at", TIMESTAMP(timezone=True), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
)

discovery_observations = Table(
    "discovery_observations",
    metadata,
    Column("observation_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("candidate_id", Uuid(as_uuid=True), nullable=False),
    Column("observed_via", Text, nullable=False),
    Column("observer_ref", Text),
    Column("claim_excerpt_hash", Text),
    Column("content_hash", Text),
    Column("corroborates_observation_id", Uuid(as_uuid=True)),
    Column("observed_at", TIMESTAMP(timezone=True), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
)

discovery_trials = Table(
    "discovery_trials",
    metadata,
    Column("trial_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("candidate_id", Uuid(as_uuid=True), nullable=False),
    Column("trial_kind", Text, nullable=False),
    Column("sandbox_profile", Text, nullable=False),
    Column("declared_network_scopes", JSONB, nullable=False),
    Column("declared_filesystem_scopes", JSONB, nullable=False),
    Column("capability_lease_id", Uuid(as_uuid=True)),
    Column("command", JSONB, nullable=False),
    Column("input_digest", Text),
    Column("outcome", Text, nullable=False),
    Column("observed_signals", JSONB, nullable=False),
    Column("evidence_pointer", Text),
    Column("started_at", TIMESTAMP(timezone=True)),
    Column("completed_at", TIMESTAMP(timezone=True)),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

discovery_qualifications = Table(
    "discovery_qualifications",
    metadata,
    Column("qualification_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("candidate_id", Uuid(as_uuid=True), nullable=False),
    Column("disposition", Text, nullable=False),
    Column("authority_ceiling", Text, nullable=False),
    Column("allowed_uses", JSONB, nullable=False),
    Column("forbidden_uses", JSONB, nullable=False),
    Column("guidance_polarity", Text, nullable=False),
    Column("rationale", Text, nullable=False),
    Column("policy_revision", Text, nullable=False),
    Column("trial_id", Uuid(as_uuid=True)),
    Column("admission_id", Uuid(as_uuid=True)),
    Column("resource_id", Uuid(as_uuid=True)),
    Column("hold_expires_at", TIMESTAMP(timezone=True)),
    Column("qualified_at", TIMESTAMP(timezone=True), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

graph_trust_projections = Table(
    "graph_trust_projections",
    metadata,
    Column("projection_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("candidate_id", Uuid(as_uuid=True)),
    Column("resource_id", Uuid(as_uuid=True)),
    Column("knowledge_node_id", Uuid(as_uuid=True)),
    Column("subject_kind", Text, nullable=False),
    Column("projected_trust", Text, nullable=False),
    Column("authority_ceiling", Text, nullable=False),
    Column("allowed_uses", JSONB, nullable=False),
    Column("forbidden_uses", JSONB, nullable=False),
    Column("guidance_polarity", Text, nullable=False),
    Column("graph_revision", Text, nullable=False),
    Column("projection_hash", Text, nullable=False),
    Column("retrievable", Boolean, nullable=False),
    Column("satisfies_positive_slots", Boolean, nullable=False),
    Column("projected_at", TIMESTAMP(timezone=True), nullable=False),
    Column("invalidated_at", TIMESTAMP(timezone=True)),
    Column("invalidation_reason", Text),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
