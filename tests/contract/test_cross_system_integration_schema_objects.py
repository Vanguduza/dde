"""EDR-0019 cross-system operational intelligence contract invariants.

These tests lock the decisions AD-051 records, in particular the four places where
the source artifact's recommendation was rejected because DDE already owned the
concept. A regression here is a duplicate-authority defect, not a style issue.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from engine.contracts.attention_candidate import AttentionCandidate
from engine.contracts.capability_gate import CapabilityGate
from engine.contracts.context_fact import ContextFact
from engine.contracts.discovery_candidate import DiscoveryCandidate
from engine.contracts.discovery_transition import DiscoveryTransition
from engine.contracts.external_effect import ExternalEffect
from engine.contracts.mission_steer_request import MissionSteerRequest
from engine.contracts.research_mission import ResearchMission
from engine.core.ids import uuid7

SCHEMAS = Path(__file__).resolve().parents[2] / "schemas" / "objects"
MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "versions"
    / "0041_cross_system_operational_intelligence.py"
)

EDR_0019_TABLES = (
    "discovery_candidates",
    "discovery_transitions",
    "discovery_observations",
    "discovery_trials",
    "discovery_qualifications",
    "research_missions",
    "research_cells",
    "research_packets",
    "research_provider_runs",
    "research_conflicts",
    "research_cursors",
    "provider_readiness_snapshots",
    "execution_placement_decisions",
    "capability_gates",
    "capability_gate_probes",
    "environment_certifications",
    "mission_steer_requests",
    "steering_barriers",
    "safe_boundary_receipts",
    "steering_impacts",
    "context_facts",
    "attention_candidates",
    "attention_preferences",
    "automation_workflow_definitions",
    "automation_workflow_releases",
    "automation_run_grants",
    "automation_runs",
    "browser_capability_sessions",
    "external_effect_verifications",
)


def _schema(name: str) -> dict:
    return json.loads((SCHEMAS / f"{name}.json").read_text(encoding="utf-8"))


def _enum(schema: dict, field: str) -> list[str]:
    prop = schema["properties"][field]
    if "enum" in prop:
        return list(prop["enum"])
    for branch in prop.get("anyOf", []):
        if "enum" in branch:
            return list(branch["enum"])
    raise AssertionError(f"{field} is not an enum")


def _now() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------- duplicate authority


def test_discovery_reuses_the_single_canonical_source_trust_vocabulary() -> None:
    """AD-051: no second trust vocabulary. Discovery reuses vekl_resources S1..S8."""
    canonical = _enum(_schema("vekl_resource"), "source_trust")
    assert canonical[0] == "S1_NORMATIVE"
    for name, field in (
        ("discovery_candidate", "source_trust"),
        ("discovery_qualification", "authority_ceiling"),
    ):
        assert _enum(_schema(name), field) == canonical, (
            f"{name}.{field} diverged from the canonical source-trust vocabulary"
        )


def test_no_dial_trust_class_is_introduced() -> None:
    for path in SCHEMAS.glob("*.json"):
        assert "T0_DIAL_PROJECT" not in path.read_text(encoding="utf-8")


def test_external_effect_status_semantics_are_unchanged() -> None:
    """The recovery-bearing status enum must survive the postcondition axis."""
    assert _enum(_schema("external_effect"), "status") == [
        "PREPARED",
        "SENT",
        "CONFIRMED",
        "FAILED",
        "UNKNOWN",
        "RECONCILING",
        "RECONCILED",
    ]


def test_postcondition_axis_is_additive_and_separate() -> None:
    states = _enum(_schema("external_effect"), "postcondition_state")
    assert "VERIFIED" in states and "REFUTED" in states
    # The postcondition axis must not leak the transport vocabulary.
    assert "CONFIRMED" not in states
    assert "RECONCILED" not in states


def test_task_status_is_not_widened_by_steering() -> None:
    """Holds live on SteeringImpact, never on the core task state machine."""
    assert "STEERING_HELD" not in _enum(_schema("task"), "status")
    assert "STEERING_HELD" in _enum(_schema("steering_impact"), "hold_state")


def test_attention_items_remains_the_single_attention_authority() -> None:
    """Candidates feed the existing governance table; they do not replace it."""
    assert _schema("attention_item")["x-dde-storage"]["table"] == "attention_items"
    candidate = _schema("attention_candidate")
    assert candidate["x-dde-storage"]["table"] == "attention_candidates"
    assert "attention_id" in candidate["properties"]


# --------------------------------------------------------------- two-axis law


def test_discovery_transitions_cannot_carry_trust() -> None:
    """Lifecycle progress may never be a route to higher trust."""
    props = _schema("discovery_transition")["properties"]
    assert "source_trust" not in props
    assert "authority_ceiling" not in props


def test_discovery_lifecycle_and_trust_are_distinct_fields() -> None:
    props = _schema("discovery_candidate")["properties"]
    assert set(_enum(_schema("discovery_candidate"), "lifecycle_state")).isdisjoint(
        _enum(_schema("discovery_candidate"), "source_trust")
    )
    assert props["lifecycle_state"] != props["source_trust"]


# --------------------------------------------------------------- tenancy + persistence


def test_every_new_table_is_tenant_and_project_scoped() -> None:
    for path in SCHEMAS.glob("*.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        storage = schema.get("x-dde-storage")
        if not storage or storage["table"] not in EDR_0019_TABLES:
            continue
        assert storage["tenant_scoped"], f"{storage['table']} is not tenant scoped"
        assert storage["project_scoped"], f"{storage['table']} is not project scoped"


def test_migration_0041_covers_every_new_table() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for table in EDR_0019_TABLES:
        assert f"CREATE TABLE {table} (" in source, (
            f"{table} missing from migration 0041"
        )
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in source
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in source


def test_migration_0041_guards_against_stage1_double_create() -> None:
    """Migration 0001 replays generated stage1 SQL, which already holds these tables.

    0041 must therefore skip creation when they are all present and refuse a partial
    schema, exactly as 0040 does. Without the guard, a build from base double-creates.
    """
    source = MIGRATION.read_text(encoding="utf-8")
    assert "_existing_0041_tables" in source
    assert "partial cross-system operational intelligence schema detected" in source
    # The creation loop must sit behind the guard, never at the top level of upgrade().
    upgrade_body = source.split("def upgrade() -> None:", 1)[1]
    guard_index = upgrade_body.index("_existing_0041_tables()")
    create_index = upgrade_body.index("for statement in _CREATE_TABLES")
    assert guard_index < create_index


def test_migration_0041_downgrade_is_idempotent_across_both_build_paths() -> None:
    """A from-base build names the postcondition check inline; a 0040 upgrade names it.

    Both shapes must drop cleanly, so every postcondition teardown uses IF EXISTS.
    """
    source = MIGRATION.read_text(encoding="utf-8")
    down_block = source.split("_EXTERNAL_EFFECT_POSTCONDITION_DOWN = (", 1)[1].split(
        ")", 1
    )[0]
    statements = [
        line
        for line in down_block.splitlines()
        if "ALTER TABLE external_effects" in line
    ]
    assert len(statements) == 4
    for statement in statements:
        assert "IF EXISTS" in statement


def test_migration_0041_matches_generated_ddl() -> None:
    """The migration is extracted from schemas/sql; it may never drift by hand."""
    generated = (
        Path(__file__).resolve().parents[2] / "schemas" / "sql" / "0001_stage1.sql"
    ).read_text(encoding="utf-8")
    source = MIGRATION.read_text(encoding="utf-8")
    for table in EDR_0019_TABLES:
        start = generated.index(f"CREATE TABLE {table} (")
        end = generated.index("\n);", start) + len("\n);")
        assert generated[start:end] in source, f"{table} DDL drifted from schemas/sql"


def test_external_effect_sqlalchemy_table_matches_the_generated_schema() -> None:
    """The hand-declared Core table must carry every generated column.

    `engine.recovery.tables.external_effects` is written by hand while the contract is
    generated from `schemas/objects`. Adding the postcondition axis to the schema
    without adding it here made every ExternalEffect insert fail with
    `CompileError: Unconsumed column names`, cascading into 82 unit failures across
    verification, workers, checkpoints, telemetry and the integration queue.
    """
    from engine.recovery.tables import external_effects

    declared = {column.name for column in external_effects.columns}
    generated = set(_schema("external_effect")["properties"])
    assert generated <= declared, f"table is missing: {sorted(generated - declared)}"


def test_discovery_tables_match_the_generated_schema() -> None:
    """Hand-written Core tables must carry every generated column.

    Same failure mode as the `external_effects` drift that cascaded into 82 unit
    failures: the contract is generated, these mappings are not.
    """
    from engine.source.discovery import tables as discovery_tables

    pairs = (
        (discovery_tables.discovery_candidates, "discovery_candidate"),
        (discovery_tables.discovery_transitions, "discovery_transition"),
        (discovery_tables.discovery_observations, "discovery_observation"),
        (discovery_tables.discovery_trials, "discovery_trial"),
        (discovery_tables.discovery_qualifications, "discovery_qualification"),
        (discovery_tables.graph_trust_projections, "graph_trust_projection"),
    )
    for table, schema_name in pairs:
        declared = {column.name for column in table.columns}
        generated = set(_schema(schema_name)["properties"])
        assert generated <= declared, (
            f"{table.name} is missing: {sorted(generated - declared)}"
        )


def test_amendment_1_tables_are_tenant_and_project_scoped() -> None:
    for schema_name in (
        "graph_trust_projection",
        "provider_model_availability",
        "adaptive_execution_run",
        "frontend_design_orchestration",
        "knowledge_borrow_grant",
    ):
        storage = _schema(schema_name)["x-dde-storage"]
        assert storage["tenant_scoped"], storage["table"]
        assert storage["project_scoped"], storage["table"]


def test_frontend_orchestration_can_never_claim_verification() -> None:
    schema = _schema("frontend_design_orchestration")
    assert _enum(schema, "authority") == ["ADVISORY"]
    checks = [c["expression"] for c in schema["x-dde-storage"]["checks"]]
    assert any("verification_satisfied" in check for check in checks)


def test_knowledge_borrowing_cannot_launder_a_project_into_itself() -> None:
    checks = [
        c["expression"]
        for c in _schema("knowledge_borrow_grant")["x-dde-storage"]["checks"]
    ]
    joined = " ".join(checks)
    assert "lender_project_id <> project_id" in joined
    assert "includes_derived_learning" in joined and "S7_DISCOVERY_ONLY" in joined


def test_borrow_grants_are_owner_explicit_only() -> None:
    assert _enum(_schema("knowledge_borrow_grant"), "authority_class") == [
        "OWNER_EXPLICIT"
    ]


# --------------------------------------------------------------- model-level invariants


def _steer(**overrides: object) -> dict:
    now = _now()
    payload = {
        "steer_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "mission_id": uuid7(),
        "authority_class": "OWNER_EXPLICIT",
        "read_only": True,
        "material": False,
        "intent_text_hash": "a" * 64,
        "intent_summary": "status question",
        "state": "RECEIVED",
        "requires_truth_change": False,
        "decision_hash": "b" * 64,
        "created_at": now,
        "updated_at": now,
    }
    payload.update(overrides)
    return payload


def test_steer_accepts_a_read_only_owner_question() -> None:
    record = MissionSteerRequest.model_validate(_steer())
    assert record.read_only is True
    assert record.barrier_id is None


def test_steer_rejects_an_unknown_authority_class() -> None:
    with pytest.raises(ValidationError):
        MissionSteerRequest.model_validate(_steer(authority_class="SELF_GRANTED"))


def test_research_mission_rejects_an_undeclared_dimension() -> None:
    now = _now()
    with pytest.raises(ValidationError):
        ResearchMission.model_validate(
            {
                "research_mission_id": uuid7(),
                "tenant_id": uuid7(),
                "project_id": uuid7(),
                "title": "ahead-of-work",
                "required_dimensions": ["ASTROLOGY"],
                "optional_dimensions": [],
                "target_unit_revisions": [],
                "status": "DRAFT",
                "mission_definition_hash": "c" * 64,
                "policy_revision": "1",
                "budget": {},
                "egress_profile": "PUBLIC",
                "cells_total": 0,
                "cells_complete": 0,
                "cells_conflicted": 0,
                "created_at": now,
                "updated_at": now,
            }
        )


def test_context_fact_authority_classes_are_closed() -> None:
    classes = _enum(_schema("context_fact"), "authority_class")
    assert classes[0] == "OWNER_CANONICAL"
    assert classes[-1] == "UNTRUSTED_EXTERNAL"
    assert "MODEL_INFERENCE" in classes


def test_browser_capability_ladder_is_ordered_and_bounded() -> None:
    levels = _enum(_schema("browser_capability_session"), "capability_level")
    assert levels == [
        "L0_FETCH_ONLY",
        "L1_DETERMINISTIC_BROWSER",
        "L2_STRUCTURED_EXTRACTION",
        "L3_SEMANTIC_ELEMENT_RESOLUTION",
        "L4_BOUNDED_DISCOVERY",
        "L5_AGENTIC_BROWSER",
    ]


def test_browser_session_can_never_claim_verification_authority() -> None:
    assert _enum(_schema("browser_capability_session"), "verification_authority") == [
        "NONE"
    ]


def test_capability_gate_degraded_contract_states_all_four_facts() -> None:
    required = _schema("capability_gate")["$defs"]["DegradedContract"]["required"]
    assert set(required) == {"broken", "still_works", "will_not_do", "restore_action"}


def test_readiness_ready_requires_evidence_at_the_database() -> None:
    checks = [
        c["expression"]
        for c in _schema("provider_readiness_snapshot")["x-dde-storage"]["checks"]
    ]
    assert any("READY" in c and "evidence_fresh" in c for c in checks)


def test_environment_certification_green_requires_the_full_chain() -> None:
    checks = [
        c["expression"]
        for c in _schema("environment_certification")["x-dde-storage"]["checks"]
    ]
    joined = " ".join(checks)
    for term in (
        "desired",
        "configured",
        "live",
        "qualified",
        "evidenced",
        "evidence_fresh",
    ):
        assert term in joined


# --------------------------------------------------------------- smoke construction


def test_core_new_contracts_construct() -> None:
    now = _now()
    tenant, project = uuid7(), uuid7()
    candidate = DiscoveryCandidate.model_validate(
        {
            "candidate_id": uuid7(),
            "tenant_id": tenant,
            "project_id": project,
            "canonical_locator": "https://github.com/example/repo",
            "normalized_identity_key": "github:example/repo",
            "identity_scheme": "GITHUB_REPOSITORY",
            "lifecycle_state": "DISCOVERED",
            "source_trust": "S7_DISCOVERY_ONLY",
            "discovered_by": "RESEARCH_MISSION",
            "discovery_refs": [],
            "observation_count": 1,
            "license_ids": [],
            "sanitizer_findings": [],
            "architecture_findings": [],
            "first_seen_at": now,
            "last_observed_at": now,
            "created_at": now,
            "updated_at": now,
        }
    )
    assert candidate.lifecycle_state == "DISCOVERED"

    transition = DiscoveryTransition.model_validate(
        {
            "transition_id": uuid7(),
            "tenant_id": tenant,
            "project_id": project,
            "candidate_id": candidate.candidate_id,
            "sequence": 1,
            "to_state": "TRIAGED",
            "reason_code": "policy.triage",
            "actor": "SYSTEM",
            "decision_hash": "d" * 64,
            "occurred_at": now,
            "created_at": now,
        }
    )
    assert transition.sequence == 1

    fact = ContextFact.model_validate(
        {
            "fact_id": uuid7(),
            "tenant_id": tenant,
            "project_id": project,
            "subject": "project.runtime",
            "predicate": "uses",
            "value": {"name": "python"},
            "authority_class": "MODEL_INFERENCE",
            "valid_from": now,
            "observed_at": now,
            "content_hash": "e" * 64,
            "created_at": now,
            "updated_at": now,
        }
    )
    assert fact.promoted_by_ref is None

    gate = CapabilityGate.model_validate(
        {
            "gate_id": uuid7(),
            "tenant_id": tenant,
            "project_id": project,
            "capability_id": "browser.fetch",
            "environment": "dev",
            "desired_state": "READY",
            "configuration_state": "COMPLETE",
            "reachability_state": "UNKNOWN",
            "qualification_state": "UNQUALIFIED",
            "readiness_state": "UNCONFIGURED",
            "blocking_scope": "NONE",
            "owner_action_required": False,
            "created_at": now,
            "updated_at": now,
        }
    )
    assert gate.readiness_state == "UNCONFIGURED"

    effect_fields = set(ExternalEffect.model_fields)
    assert {"postcondition_policy", "postcondition_state"} <= effect_fields

    candidate_item = AttentionCandidate.model_validate(
        {
            "candidate_id": uuid7(),
            "tenant_id": tenant,
            "project_id": project,
            "attention_class": "SECURITY",
            "dedupe_key": "provider:x:rate_limit",
            "summary": "rate limited",
            "importance": 1.0,
            "urgency": 1.0,
            "actionability": 1.0,
            "novelty": 1.0,
            "confidence": 1.0,
            "blast_radius": 1.0,
            "time_sensitivity": 1.0,
            "owner_required": True,
            "repeat_penalty": 0.0,
            "score": 1.0,
            "repeat_count": 1,
            "first_seen_at": now,
            "last_seen_at": now,
            "disposition": "PENDING",
            "bypassed_budget": True,
            "created_at": now,
            "updated_at": now,
        }
    )
    assert candidate_item.bypassed_budget is True
