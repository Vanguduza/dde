"""Deterministic Production VEKL Unit/GraphRAG/TruthChallenge policy proof."""

from __future__ import annotations

from uuid import uuid4

import pytest

from engine.core.errors import DdeError
from engine.vekl.knowledge import (
    CONCERN_CLASSIFIER_VERSION,
    GRAPH_COMPILER_VERSION,
    HYBRID_RANKER_VERSION,
    RETRIEVAL_ROUTE_POLICY_HASH,
    challenge_eligibility,
    classify_concerns,
    resolution_envelope,
    selection_role,
    unit_lineage_id,
    unit_revision_hash,
    validate_truth_patch,
)


def test_unit_lineage_is_stable_while_revision_tracks_authority_changes() -> None:
    tenant_id = uuid4()
    project_id = uuid4()
    task_ids = [uuid4(), uuid4()]
    lineage_a = unit_lineage_id(
        tenant_id=tenant_id,
        project_id=project_id,
        feature_refs=["feature:checkout"],
        realization_facets=["backend", "verification"],
        fallback_task_ids=task_ids,
    )
    lineage_b = unit_lineage_id(
        tenant_id=tenant_id,
        project_id=project_id,
        feature_refs=["feature:checkout"],
        realization_facets=["verification", "backend"],
        fallback_task_ids=[uuid4()],
    )
    assert lineage_a == lineage_b
    fallback_a = unit_lineage_id(
        tenant_id=tenant_id,
        project_id=project_id,
        feature_refs=[],
        realization_facets=["implementation"],
        fallback_task_ids=task_ids,
    )
    fallback_b = unit_lineage_id(
        tenant_id=tenant_id,
        project_id=project_id,
        feature_refs=[],
        realization_facets=["implementation"],
        fallback_task_ids=list(reversed(task_ids)),
    )
    assert fallback_a == fallback_b
    revision_a = unit_revision_hash(
        lineage_id=lineage_a,
        task_graph_version=1,
        project_truth_hash="truth-a",
        applicable_truth_slice_hash="slice-a",
        stack_fingerprint_hash="stack-a",
        contract_set_hash="contract-a",
        product_experience_hash=None,
    )
    revision_b = unit_revision_hash(
        lineage_id=lineage_a,
        task_graph_version=1,
        project_truth_hash="truth-b",
        applicable_truth_slice_hash="slice-a",
        stack_fingerprint_hash="stack-a",
        contract_set_hash="contract-a",
        product_experience_hash=None,
    )
    assert revision_a != revision_b


def test_concern_classifier_and_selection_role_are_deterministic() -> None:
    concerns = classify_concerns(
        title="Secure checkout API migration",
        intent="Migrate PostgreSQL checkout endpoints and verify authorization",
        task_class="implementation",
        read_scope=["engine/payments", "engine/auth"],
        write_scope=["migrations", "engine/api"],
    )
    assert concerns == (
        "SECURITY",
        "AUTH",
        "PAYMENTS",
        "DATABASE",
        "MIGRATION",
        "BACKEND_API",
    )
    purpose, role = selection_role(
        resource_kind="OFFICIAL_DOC",
        activation_mode="READ_ONLY_CONTEXT",
        purpose="DATABASE:route.database.v1",
    )
    assert purpose == "DATABASE:route.database.v1"
    assert role == "NORMATIVE_REFERENCE"


def test_resolution_envelope_pins_every_nondeterministic_boundary() -> None:
    index_id = uuid4()
    envelope = resolution_envelope(
        graph_hash="graph-hash",
        context_index_id=index_id,
        context_index_version="index-v7",
        embedding_model_version="embed-v3",
    )
    assert envelope["concern_classifier_version"] == CONCERN_CLASSIFIER_VERSION
    assert envelope["retrieval_route_policy_hash"] == RETRIEVAL_ROUTE_POLICY_HASH
    assert envelope["graph_compiler_version"] == GRAPH_COMPILER_VERSION
    assert envelope["hybrid_ranker_version"] == HYBRID_RANKER_VERSION
    assert envelope["context_index_id"] == str(index_id)
    assert envelope["context_index_version"] == "index-v7"
    assert envelope["embedding_model_version"] == "embed-v3"
    assert envelope["stable_tie_break_rule"]


def test_truth_challenge_threshold_is_explicit_and_not_popularity_based() -> None:
    first_party = challenge_eligibility(
        classification="TRUTH_CONFLICT_SIGNAL",
        source_trust="S2_FIRST_PARTY",
        provenance_valid=True,
        stale=False,
        corroboration_count=0,
        deterministic_reproduction=False,
    )
    assert first_party.eligible is True
    community_single = challenge_eligibility(
        classification="TRUTH_CONFLICT_SIGNAL",
        source_trust="S5_MAINTAINER_COMMUNITY",
        provenance_valid=True,
        stale=False,
        corroboration_count=1,
        deterministic_reproduction=False,
    )
    assert community_single.eligible is False
    community_correlated = challenge_eligibility(
        classification="TRUTH_CONFLICT_SIGNAL",
        source_trust="S5_MAINTAINER_COMMUNITY",
        provenance_valid=True,
        stale=False,
        corroboration_count=2,
        deterministic_reproduction=False,
    )
    assert community_correlated.eligible is True
    discovery = challenge_eligibility(
        classification="TRUTH_CONFLICT_SIGNAL",
        source_trust="S7_DISCOVERY_ONLY",
        provenance_valid=True,
        stale=False,
        corroboration_count=50,
        deterministic_reproduction=False,
    )
    assert discovery.eligible is False


def test_truth_patch_requires_exact_governed_change_and_supersession() -> None:
    assert (
        validate_truth_patch(
            {
                "truth_change_kind": "EDR_SUPERSEDE",
                "exact_truth_patch": {"slug": "EDR-new"},
                "verification_plan": ["contract", "integration"],
            }
        )
        == "EDR_SUPERSEDE"
    )
    with pytest.raises(DdeError) as caught:
        validate_truth_patch(
            {
                "truth_change_kind": "EDR_AMEND",
                "exact_truth_patch": {"edr_id": str(uuid4())},
                "verification_plan": ["contract"],
            }
        )
    assert caught.value.error_code == "VEKL_TRUTH_PATCH_INVALID"
    with pytest.raises(DdeError):
        validate_truth_patch(
            {
                "truth_change_kind": "REQUIREMENT_ADD",
                "exact_truth_patch": {},
                "verification_plan": ["contract"],
            }
        )
