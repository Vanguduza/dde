"""VEKL 2.2 architecture invariants that do not require PostgreSQL.

These are acceptance guards, not implementation-detail tests: stable Unit lineage,
immutable revisions, a pinned GraphRAG envelope, closed graph vocabulary, fail-closed
canon authority and append-only knowledge-resolution evidence.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from engine.contracts.vekl_knowledge_edge import VEKLKnowledgeEdge
from engine.contracts.vekl_knowledge_node import VEKLKnowledgeNode
from engine.contracts.vekl_resolution_trace import VEKLResolutionTrace
from engine.contracts.vekl_unit_map import VEKLUnitMap
from engine.core.errors import DdeError
from engine.gateway.scopes import COMMAND_SCOPES
from engine.governance.types import STANDING_FORBIDDEN_TYPES
from engine.vekl.knowledge import (
    GRAPH_SCHEMA_VERSION,
    HARD_PRODUCT_QUALITY_GATES,
    QUALITATIVE_ESCALATION,
    QUALITATIVE_PRODUCT_QUALITY_GATES,
    RETRIEVAL_ROUTE_POLICY_HASH,
    STABLE_TIE_BREAK_RULE,
    TRUTH_DECISION_CLASS,
    TRUTH_DECISION_ROLE,
    TRUTH_REVIEWER_CLASS,
    UNIT_SCHEMA_VERSION,
    challenge_eligibility,
    resolution_envelope,
    unit_lineage_id,
    unit_revision_hash,
    validate_truth_patch,
)
from engine.vekl.knowledge_repository import VEKLKnowledgeRepository, _db_values
from engine.vekl.models import TruthChallengeSpec
from engine.vekl.tables import vekl_unit_maps

NOW = datetime.now(UTC)
TENANT = uuid4()
PROJECT = uuid4()


def test_jsonb_repository_normalizes_uuid_references() -> None:
    unit_id = uuid4()
    task_id = uuid4()
    graph_id = uuid4()
    stack_id = uuid4()
    workspace_id = uuid4()
    record = VEKLUnitMap(
        unit_map_id=unit_id,
        tenant_id=TENANT,
        project_id=PROJECT,
        mission_id=uuid4(),
        task_graph_id=graph_id,
        task_graph_version=1,
        task_ids=[task_id],
        unit_lineage_id="lineage",
        unit_revision_hash="revision",
        unit_boundary_policy_version="v1",
        unit_projection_compiler_version="v1",
        project_truth_hash="truth",
        applicable_truth_slice_hash="slice",
        stack_fingerprint_id=stack_id,
        stack_fingerprint_hash="stack",
        contract_set_hash="contracts",
        retrieval_route_policy_hash="route",
        objective="Implement checkout",
        scope={"task_id": task_id},
        requirement_refs=["REQ-1"],
        edr_refs=[],
        constitution_refs=[],
        upstream_task_refs=[task_id],
        downstream_task_refs=[],
        contracts_consumed=[],
        contracts_produced=[],
        code_targets=[],
        workspace_refs=[workspace_id],
        product_experience_refs=[],
        security_refs=[],
        eventuality_refs=[],
        research_questions=[],
        knowledge_route_ids=[],
        required_verifiers=[],
        knowledge_readiness_state="MAPPING",
        challenge_state="NONE",
        unit_map_hash="map",
        created_at=NOW,
        updated_at=NOW,
        invalidation_reasons=[],
    )

    values = _db_values(vekl_unit_maps, record)

    assert values["unit_map_id"] == unit_id
    assert values["task_graph_id"] == graph_id
    assert values["stack_fingerprint_id"] == stack_id
    assert values["task_ids"] == [str(task_id)]
    assert values["upstream_task_refs"] == [str(task_id)]
    assert values["workspace_refs"] == [str(workspace_id)]
    assert values["scope"] == {"task_id": str(task_id)}


def test_unit_lineage_is_canonical_and_independent_of_task_order() -> None:
    task_a, task_b = uuid4(), uuid4()
    first = unit_lineage_id(
        tenant_id=TENANT,
        project_id=PROJECT,
        feature_refs=["feature.checkout", "feature.cart", "feature.checkout"],
        realization_facets=["verification", "implementation"],
        fallback_task_ids=[task_a, task_b],
    )
    reordered = unit_lineage_id(
        tenant_id=TENANT,
        project_id=PROJECT,
        feature_refs=["feature.cart", "feature.checkout"],
        realization_facets=["implementation", "verification"],
        fallback_task_ids=[task_b, task_a],
    )
    assert first == reordered


def test_unit_lineage_uses_task_membership_only_as_featureless_fallback() -> None:
    task_a, task_b = uuid4(), uuid4()
    with_feature_a = unit_lineage_id(
        tenant_id=TENANT,
        project_id=PROJECT,
        feature_refs=["feature.checkout"],
        realization_facets=["implementation"],
        fallback_task_ids=[task_a],
    )
    with_feature_b = unit_lineage_id(
        tenant_id=TENANT,
        project_id=PROJECT,
        feature_refs=["feature.checkout"],
        realization_facets=["implementation"],
        fallback_task_ids=[task_b],
    )
    assert with_feature_a == with_feature_b
    featureless_a = unit_lineage_id(
        tenant_id=TENANT,
        project_id=PROJECT,
        feature_refs=[],
        realization_facets=["implementation"],
        fallback_task_ids=[task_a],
    )
    featureless_b = unit_lineage_id(
        tenant_id=TENANT,
        project_id=PROJECT,
        feature_refs=[],
        realization_facets=["implementation"],
        fallback_task_ids=[task_b],
    )
    assert featureless_a != featureless_b


def test_unit_revision_changes_without_changing_lineage() -> None:
    lineage = unit_lineage_id(
        tenant_id=TENANT,
        project_id=PROJECT,
        feature_refs=["feature.checkout"],
        realization_facets=["implementation"],
        fallback_task_ids=[],
    )

    def revision(
        *,
        truth_hash: str = "truth-a",
        stack_hash: str = "stack-a",
        contracts_hash: str = "contracts-a",
        route_policy_hash: str = RETRIEVAL_ROUTE_POLICY_HASH,
        graph_schema_version: str = GRAPH_SCHEMA_VERSION,
        unit_schema_version: str = UNIT_SCHEMA_VERSION,
    ) -> str:
        return unit_revision_hash(
            lineage_id=lineage,
            task_graph_version=4,
            project_truth_hash=truth_hash,
            applicable_truth_slice_hash="slice-a",
            stack_fingerprint_hash=stack_hash,
            contract_set_hash=contracts_hash,
            product_experience_hash="px-a",
            retrieval_route_policy_hash=route_policy_hash,
            graph_schema_version=graph_schema_version,
            unit_schema_version=unit_schema_version,
        )

    original = revision()
    assert revision(truth_hash="truth-b") != original
    assert revision(stack_hash="stack-b") != original
    assert revision(contracts_hash="contracts-b") != original
    assert revision(route_policy_hash="route-policy-b") != original
    assert revision(graph_schema_version=GRAPH_SCHEMA_VERSION + ".next") != original
    assert revision(unit_schema_version=UNIT_SCHEMA_VERSION + ".next") != original


def test_graphrag_determinism_envelope_pins_all_result_affecting_components() -> None:
    envelope = resolution_envelope(
        graph_hash="graph-a",
        context_index_id=uuid4(),
        context_index_version="17",
        embedding_model_version="embedding-a",
    )
    required = {
        "concern_classifier_id",
        "concern_classifier_version",
        "retrieval_route_registry_version",
        "retrieval_route_policy_hash",
        "graph_compiler_version",
        "graph_snapshot_hash",
        "chunking_algorithm_version",
        "embedding_model_version",
        "context_index_id",
        "context_index_version",
        "lexical_retriever_version",
        "hybrid_ranker_version",
        "ranking_weights_hash",
        "hard_eligibility_policy_hash",
        "stable_tie_break_rule",
        "resource_outcome_policy_version",
    }
    assert set(envelope) == required
    assert envelope["retrieval_route_policy_hash"] == RETRIEVAL_ROUTE_POLICY_HASH
    assert envelope["stable_tie_break_rule"] == STABLE_TIE_BREAK_RULE
    assert envelope == resolution_envelope(
        graph_hash="graph-a",
        context_index_id=__import__("uuid").UUID(str(envelope["context_index_id"])),
        context_index_version="17",
        embedding_model_version="embedding-a",
    )


def test_graph_vocabulary_is_closed_by_wire_contract() -> None:
    with pytest.raises(ValidationError):
        VEKLKnowledgeNode.model_validate(
            {
                "knowledge_node_id": uuid4(),
                "tenant_id": TENANT,
                "project_id": PROJECT,
                "node_kind": "UNIT",
                "object_type": "unit",
                "stable_ref": "unit:x",
                "authority_class": "PROJECTION",
                "authority_service": "VEKL",
                "content_hash": "hash",
                "projection_compiler_version": "v1",
                "metadata": {},
                "created_at": NOW,
                "updated_at": NOW,
            }
        )
    with pytest.raises(ValidationError):
        VEKLKnowledgeEdge.model_validate(
            {
                "knowledge_edge_id": uuid4(),
                "tenant_id": TENANT,
                "project_id": PROJECT,
                "from_node_id": uuid4(),
                "relationship": "some_future_alias",
                "to_node_id": uuid4(),
                "provenance_ref": "test",
                "provenance_hash": "hash",
                "derivation_class": "DETERMINISTIC",
                "created_at": NOW,
                "updated_at": NOW,
            }
        )


def test_challenge_prefilter_cannot_be_bypassed_by_model_confidence() -> None:
    rejected = challenge_eligibility(
        classification="TRUTH_CONFLICT_SIGNAL",
        source_trust="S4_COMMUNITY",
        provenance_valid=True,
        stale=False,
        corroboration_count=0,
        deterministic_reproduction=False,
    )
    assert not rejected.eligible
    accepted = challenge_eligibility(
        classification="TRUTH_CONFLICT_SIGNAL",
        source_trust="S2_FIRST_PARTY",
        provenance_valid=True,
        stale=False,
        corroboration_count=1,
        deterministic_reproduction=False,
    )
    assert accepted.eligible


def test_locked_decision_mutation_is_not_an_admitted_truth_patch() -> None:
    with pytest.raises(DdeError) as caught:
        validate_truth_patch(
            {
                "truth_change_kind": "EDR_AMEND",
                "exact_truth_patch": {"slug": "EDR-0001"},
                "verification_plan": {"tests": ["contract"]},
            }
        )
    assert caught.value.error_code == "VEKL_TRUTH_PATCH_INVALID"


def test_canon_decision_role_is_not_client_selectable_and_never_standing() -> None:
    assert TRUTH_DECISION_CLASS == "PROJECT_TRUTH_CHANGE_DECISION"
    assert TRUTH_REVIEWER_CLASS == "HUMAN_PROJECT_PRINCIPAL"
    assert TRUTH_DECISION_ROLE == "approval.decide"
    assert "project_truth_change" in STANDING_FORBIDDEN_TYPES
    assert COMMAND_SCOPES["vekl.truth.challenge.decide"] == "approval.decide"
    with pytest.raises(ValidationError):
        TruthChallengeSpec.model_validate(
            {
                "finding_ids": [uuid4()],
                "challenge_class": "ARCHITECTURE_CHALLENGE",
                "severity": "HIGH",
                "conflict": {},
                "confidence": {},
                "impact": {},
                "proposal": {},
                "required_role": "approval.decide",
            }
        )


def test_resolution_trace_contract_is_immutable_and_repository_has_no_update_path() -> (
    None
):
    fields = VEKLResolutionTrace.model_fields
    assert "updated_at" not in fields
    assert "activation_manifest_id" not in fields
    assert "activation_manifest_hash" not in fields
    assert "context_package_id" not in fields
    assert "context_package_hash" not in fields
    assert not hasattr(VEKLKnowledgeRepository, "bind_trace_execution")


def test_product_quality_gates_separate_deterministic_from_qualitative_authority() -> (
    None
):
    assert HARD_PRODUCT_QUALITY_GATES == (
        "frontend_contract_pxg_completeness",
        "screen_audit_structural",
        "silhouette",
    )
    assert QUALITATIVE_PRODUCT_QUALITY_GATES == ("visual_critique",)
    assert QUALITATIVE_ESCALATION == "prototype_pixel_signoff"
    assert "visual_critique" not in HARD_PRODUCT_QUALITY_GATES


def test_change_impact_invalidates_only_matching_unit_contract_task_or_path() -> None:
    from engine.contracts.vekl_unit_map import VEKLUnitMap
    from engine.vekl.knowledge_service import VEKLKnowledgeService
    from engine.vekl.models import ChangeImpactSpec

    task_id = uuid4()
    upstream = uuid4()
    unit = VEKLUnitMap(
        unit_map_id=uuid4(),
        tenant_id=TENANT,
        project_id=PROJECT,
        mission_id=uuid4(),
        task_graph_id=uuid4(),
        task_graph_version=4,
        task_ids=[task_id],
        unit_lineage_id="lineage",
        unit_revision_hash="revision",
        unit_boundary_policy_version="boundary",
        unit_projection_compiler_version="compiler",
        project_truth_hash="truth",
        applicable_truth_slice_hash="slice",
        stack_fingerprint_id=uuid4(),
        stack_fingerprint_hash="stack",
        contract_set_hash="contracts",
        product_experience_hash=None,
        retrieval_route_policy_hash=RETRIEVAL_ROUTE_POLICY_HASH,
        objective="checkout",
        scope={"includes": ["engine/payments/**"], "reads": ["schemas/payments.json"]},
        requirement_refs=[],
        edr_refs=[],
        constitution_refs=[],
        upstream_task_refs=[upstream],
        downstream_task_refs=[],
        contracts_consumed=["contract.payment.v1"],
        contracts_produced=["event.payment-settled.v1"],
        code_targets=["engine/payments/**"],
        workspace_refs=[],
        product_experience_refs=[],
        security_refs=[],
        eventuality_refs=[],
        research_questions=[],
        knowledge_route_ids=[],
        required_verifiers=[],
        knowledge_readiness_state="READY",
        knowledge_exemption=None,
        challenge_state="CLEAR",
        unit_map_hash="map",
        created_at=NOW,
        updated_at=NOW,
        invalidated_at=None,
        invalidation_reasons=[],
    )
    contract = ChangeImpactSpec(
        source_change_ref="change-packet:123",
        source_change_hash="change-hash",
        changed_contract_refs=["contract.payment.v1"],
    )
    assert VEKLKnowledgeService._unit_matches_change(unit, contract)["contracts"] == [
        "contract.payment.v1"
    ]
    task = ChangeImpactSpec(
        source_change_ref="change-packet:124",
        source_change_hash="change-hash-2",
        changed_task_refs=[upstream],
    )
    assert VEKLKnowledgeService._unit_matches_change(unit, task)["tasks"] == [
        str(upstream)
    ]
    path = ChangeImpactSpec(
        source_change_ref="change-packet:125",
        source_change_hash="change-hash-3",
        changed_paths=["engine/payments/service.py"],
    )
    assert VEKLKnowledgeService._unit_matches_change(unit, path)["paths"] == [
        "engine/payments/service.py"
    ]
    unrelated = ChangeImpactSpec(
        source_change_ref="change-packet:126",
        source_change_hash="change-hash-4",
        changed_contract_refs=["contract.catalog.v1"],
        changed_paths=["engine/catalog/service.py"],
    )
    assert not any(VEKLKnowledgeService._unit_matches_change(unit, unrelated).values())
    assert COMMAND_SCOPES["vekl.knowledge.invalidate_from_change"] == "mission.control"


def test_activation_manifest_table_exposes_knowledge_context() -> None:
    from engine.vekl.tables import vekl_activation_manifests

    assert "knowledge_context" in vekl_activation_manifests.c
