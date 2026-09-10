"""Deterministic Production VEKL knowledge-topology primitives.

These helpers compile projection identities, retrieval policy and challenge eligibility.
They do not own Task state, Project Truth, source admission, activation or verification.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

from engine.core.errors import DdeError
from engine.core.hashing import canonical_json, sha256_hex

UNIT_BOUNDARY_POLICY_VERSION = "vekl-unit-boundary-feature-coherent-v1"
UNIT_PROJECTION_COMPILER_VERSION = "vekl-unit-projection-v2"
GRAPH_COMPILER_VERSION = "vekl-knowledge-graph-v2"
GRAPH_SCHEMA_VERSION = "vekl-graph-schema-v1"
UNIT_SCHEMA_VERSION = "vekl-unit-schema-v1"
TRUTH_DECISION_CLASS = "PROJECT_TRUTH_CHANGE_DECISION"
TRUTH_REVIEWER_CLASS = "HUMAN_PROJECT_PRINCIPAL"
TRUTH_DECISION_ROLE = "approval.decide"
CONCERN_CLASSIFIER_VERSION = "vekl-concern-classifier-v1"
ROUTE_REGISTRY_VERSION = "vekl-retrieval-routes-v1"
LEXICAL_RETRIEVER_VERSION = "dde-lexical-v1"
HYBRID_RANKER_VERSION = "vekl-hybrid-ranker-v1"
RESOURCE_OUTCOME_POLICY_VERSION = "vekl-resource-outcome-v1"
STABLE_TIE_BREAK_RULE = "score-desc-resource-id-desc"
ELIGIBILITY_POLICY_VERSION = "vekl-eligibility-v1"
CHUNKING_ALGORITHM_VERSION = "dde-context-chunker-v1"

# Product-quality evaluation is deliberately split. Structural/completeness gates are
# deterministic authorities; aesthetic judgment remains with the existing visual critic
# and bounded human pixel-signoff fallback. VEKL routes these gates but does not invent
# another visual authority.
HARD_PRODUCT_QUALITY_GATES = (
    "frontend_contract_pxg_completeness",
    "screen_audit_structural",
    "silhouette",
)
QUALITATIVE_PRODUCT_QUALITY_GATES = ("visual_critique",)
QUALITATIVE_ESCALATION = "prototype_pixel_signoff"

CONCERN_ORDER = (
    "SECURITY",
    "AUTH",
    "PAYMENTS",
    "DATABASE",
    "MIGRATION",
    "WEB_UI",
    "MOBILE_UI",
    "DESIGN",
    "ACCESSIBILITY",
    "BACKEND_API",
    "TESTING",
    "PERFORMANCE",
    "OBSERVABILITY",
    "DEPLOYMENT",
    "INCIDENT",
    "PACKAGE_UPGRADE",
    "DONOR_REUSE",
    "GENERIC_IMPLEMENTATION",
)

_ROUTE_POLICIES: dict[str, dict[str, object]] = {
    "WEB_UI": {
        "relations": ["governed_by", "constrained_by", "supports", "verified_by"],
        "resource_kinds": [
            "OFFICIAL_DOC",
            "SKILL",
            "TEMPLATE",
            "REFERENCE_ARCHITECTURE",
            "TEST_ORACLE",
            "TOOL",
        ],
        "roles": [
            "NORMATIVE_REFERENCE",
            "IMPLEMENTATION_GUIDANCE",
            "PROCEDURAL_SKILL",
            "VERIFIER",
        ],
    },
    "MOBILE_UI": {
        "relations": ["governed_by", "constrained_by", "supports", "verified_by"],
        "resource_kinds": [
            "OFFICIAL_DOC",
            "SKILL",
            "TEMPLATE",
            "REFERENCE_ARCHITECTURE",
            "TEST_ORACLE",
            "TOOL",
        ],
        "roles": [
            "NORMATIVE_REFERENCE",
            "IMPLEMENTATION_GUIDANCE",
            "PROCEDURAL_SKILL",
            "VERIFIER",
        ],
    },
    "DESIGN": {
        "relations": ["realizes", "constrained_by", "governed_by", "supports"],
        "resource_kinds": [
            "OFFICIAL_DOC",
            "SKILL",
            "TEMPLATE",
            "REFERENCE_ARCHITECTURE",
            "TEST_ORACLE",
        ],
        "roles": [
            "NORMATIVE_REFERENCE",
            "IMPLEMENTATION_GUIDANCE",
            "PROCEDURAL_SKILL",
            "VERIFIER",
        ],
    },
    "ACCESSIBILITY": {
        "relations": ["constrained_by", "supports", "verified_by"],
        "resource_kinds": ["SPEC", "OFFICIAL_DOC", "SKILL", "TEST_ORACLE", "TOOL"],
        "roles": ["NORMATIVE_REFERENCE", "PROCEDURAL_SKILL", "VERIFIER"],
    },
    "BACKEND_API": {
        "relations": ["consumes", "produces", "supports", "verified_by"],
        "resource_kinds": [
            "SPEC",
            "OFFICIAL_DOC",
            "SKILL",
            "PACKAGE",
            "REPOSITORY",
            "TEST_ORACLE",
            "TOOL",
        ],
        "roles": [
            "NORMATIVE_REFERENCE",
            "IMPLEMENTATION_GUIDANCE",
            "PROCEDURAL_SKILL",
            "VERIFIER",
        ],
    },
    "DATABASE": {
        "relations": ["consumes", "produces", "supports", "verified_by"],
        "resource_kinds": [
            "SPEC",
            "OFFICIAL_DOC",
            "SKILL",
            "PACKAGE",
            "DEPLOYMENT_RECIPE",
            "TEST_ORACLE",
            "TOOL",
        ],
        "roles": [
            "NORMATIVE_REFERENCE",
            "IMPLEMENTATION_GUIDANCE",
            "PROCEDURAL_SKILL",
            "VERIFIER",
        ],
    },
    "AUTH": {
        "relations": ["governed_by", "consumes", "supports", "verified_by"],
        "resource_kinds": [
            "SPEC",
            "OFFICIAL_DOC",
            "SKILL",
            "SECURITY_FEED",
            "TEST_ORACLE",
            "TOOL",
        ],
        "roles": ["NORMATIVE_REFERENCE", "SECURITY", "PROCEDURAL_SKILL", "VERIFIER"],
    },
    "SECURITY": {
        "relations": ["governed_by", "supports", "verifies", "diagnoses"],
        "resource_kinds": [
            "SPEC",
            "OFFICIAL_DOC",
            "SECURITY_FEED",
            "SKILL",
            "TEST_ORACLE",
            "TOOL",
        ],
        "roles": ["NORMATIVE_REFERENCE", "SECURITY", "DIAGNOSTIC", "VERIFIER"],
    },
    "PAYMENTS": {
        "relations": ["governed_by", "consumes", "supports", "verified_by"],
        "resource_kinds": [
            "SPEC",
            "OFFICIAL_DOC",
            "SECURITY_FEED",
            "SKILL",
            "TEST_ORACLE",
        ],
        "roles": [
            "NORMATIVE_REFERENCE",
            "SECURITY",
            "IMPLEMENTATION_GUIDANCE",
            "VERIFIER",
        ],
    },
    "MIGRATION": {
        "relations": ["consumes", "produces", "supports", "verified_by"],
        "resource_kinds": [
            "OFFICIAL_DOC",
            "SKILL",
            "DEPLOYMENT_RECIPE",
            "TEST_ORACLE",
            "TOOL",
        ],
        "roles": [
            "IMPLEMENTATION_GUIDANCE",
            "PROCEDURAL_SKILL",
            "RECOVERY",
            "VERIFIER",
        ],
    },
    "TESTING": {
        "relations": ["verified_by", "verifies", "supports"],
        "resource_kinds": ["OFFICIAL_DOC", "SKILL", "TEST_ORACLE", "TOOL"],
        "roles": ["PROCEDURAL_SKILL", "VERIFIER", "DIAGNOSTIC"],
    },
    "PERFORMANCE": {
        "relations": ["supports", "verifies", "diagnoses"],
        "resource_kinds": [
            "OFFICIAL_DOC",
            "SKILL",
            "TOOL",
            "OBSERVABILITY_INTEGRATION",
            "TEST_ORACLE",
        ],
        "roles": ["IMPLEMENTATION_GUIDANCE", "DIAGNOSTIC", "OBSERVABILITY", "VERIFIER"],
    },
    "OBSERVABILITY": {
        "relations": ["supports", "diagnoses", "verifies"],
        "resource_kinds": [
            "OFFICIAL_DOC",
            "SKILL",
            "TOOL",
            "OBSERVABILITY_INTEGRATION",
        ],
        "roles": ["OBSERVABILITY", "DIAGNOSTIC", "IMPLEMENTATION_GUIDANCE"],
    },
    "DEPLOYMENT": {
        "relations": ["supports", "consumes", "verified_by"],
        "resource_kinds": [
            "OFFICIAL_DOC",
            "SKILL",
            "DEPLOYMENT_RECIPE",
            "TOOL",
            "TEST_ORACLE",
        ],
        "roles": ["DEPLOYMENT", "RECOVERY", "VERIFIER"],
    },
    "INCIDENT": {
        "relations": ["diagnoses", "supports", "verifies"],
        "resource_kinds": [
            "OFFICIAL_DOC",
            "SECURITY_FEED",
            "ISSUE",
            "DISCUSSION",
            "SKILL",
            "TOOL",
        ],
        "roles": ["DIAGNOSTIC", "RECOVERY", "SECURITY"],
    },
    "PACKAGE_UPGRADE": {
        "relations": ["supports", "supersedes", "verified_by"],
        "resource_kinds": [
            "PACKAGE_METADATA",
            "OFFICIAL_DOC",
            "SECURITY_FEED",
            "SKILL",
            "TEST_ORACLE",
        ],
        "roles": [
            "NORMATIVE_REFERENCE",
            "SECURITY",
            "IMPLEMENTATION_GUIDANCE",
            "VERIFIER",
        ],
    },
    "DONOR_REUSE": {
        "relations": ["supplies", "supports", "verified_by"],
        "resource_kinds": ["REPOSITORY", "TEMPLATE", "REFERENCE_ARCHITECTURE"],
        "roles": ["REUSE_CANDIDATE", "IMPLEMENTATION_GUIDANCE"],
    },
    "GENERIC_IMPLEMENTATION": {
        "relations": ["governed_by", "supports", "verified_by"],
        "resource_kinds": [
            "SPEC",
            "OFFICIAL_DOC",
            "SKILL",
            "REFERENCE_ARCHITECTURE",
            "TEST_ORACLE",
            "TOOL",
        ],
        "roles": [
            "NORMATIVE_REFERENCE",
            "IMPLEMENTATION_GUIDANCE",
            "PROCEDURAL_SKILL",
            "VERIFIER",
        ],
    },
}

RETRIEVAL_ROUTE_POLICY_HASH = sha256_hex(
    canonical_json({"version": ROUTE_REGISTRY_VERSION, "routes": _ROUTE_POLICIES})
)
RANKING_WEIGHTS_HASH = sha256_hex(
    canonical_json(
        {
            "version": HYBRID_RANKER_VERSION,
            "weights": {"exact": 4, "trust": 3, "task": 2, "freshness": 1},
        }
    )
)
ELIGIBILITY_POLICY_HASH = sha256_hex(ELIGIBILITY_POLICY_VERSION)


def deterministic_uuid(kind: str, payload: object) -> UUID:
    return uuid5(
        NAMESPACE_URL, f"dde:vekl:{kind}:{sha256_hex(canonical_json(payload))}"
    )


def unit_lineage_id(
    *,
    tenant_id: UUID,
    project_id: UUID,
    feature_refs: list[str],
    realization_facets: list[str],
    fallback_task_ids: list[UUID] | None = None,
    boundary_policy_version: str = UNIT_BOUNDARY_POLICY_VERSION,
) -> str:
    """Stable conceptual Unit identity.

    Mutable Project Truth, TaskGraph revision, stack, route policy and graph compiler
    state are deliberately excluded. Canonical membership ordering is lexical and
    duplicate-insensitive so dependency/topological order cannot churn lineage.
    """
    features = sorted(set(feature_refs))
    facets = sorted(set(realization_facets))
    fallback = sorted({str(item) for item in (fallback_task_ids or [])})
    if not features and not fallback:
        raise DdeError(
            "VEKL_UNIT_INVALID",
            "unit lineage requires canonical feature membership or a task fallback",
        )
    return sha256_hex(
        canonical_json(
            {
                "tenant_id": str(tenant_id),
                "project_id": str(project_id),
                "feature_refs": features,
                "realization_facets": facets,
                "fallback_task_ids": fallback if not features else [],
                "boundary_policy_version": boundary_policy_version,
            }
        )
    )


def unit_revision_hash(
    *,
    lineage_id: str,
    task_graph_version: int,
    project_truth_hash: str,
    applicable_truth_slice_hash: str,
    stack_fingerprint_hash: str,
    contract_set_hash: str,
    product_experience_hash: str | None,
    retrieval_route_policy_hash: str = RETRIEVAL_ROUTE_POLICY_HASH,
    compiler_version: str = UNIT_PROJECTION_COMPILER_VERSION,
    graph_schema_version: str = GRAPH_SCHEMA_VERSION,
    unit_schema_version: str = UNIT_SCHEMA_VERSION,
) -> str:
    """Immutable identity for one exact Unit knowledge revision."""
    return sha256_hex(
        canonical_json(
            {
                "unit_lineage_id": lineage_id,
                "task_graph_version": task_graph_version,
                "project_truth_hash": project_truth_hash,
                "applicable_truth_slice_hash": applicable_truth_slice_hash,
                "stack_fingerprint_hash": stack_fingerprint_hash,
                "contract_set_hash": contract_set_hash,
                "product_experience_hash": product_experience_hash,
                "retrieval_route_policy_hash": retrieval_route_policy_hash,
                "unit_projection_compiler_version": compiler_version,
                "graph_schema_version": graph_schema_version,
                "unit_schema_version": unit_schema_version,
            }
        )
    )


def graph_snapshot_hash(
    nodes: list[dict[str, object]], edges: list[dict[str, object]]
) -> str:
    def cleaned(row: dict[str, object]) -> dict[str, object]:
        return {
            key: value
            for key, value in row.items()
            if key not in {"created_at", "updated_at", "invalidated_at"}
        }

    return sha256_hex(
        canonical_json(
            {
                "nodes": sorted(
                    (cleaned(item) for item in nodes),
                    key=lambda item: str(item.get("knowledge_node_id", "")),
                ),
                "edges": sorted(
                    (cleaned(item) for item in edges),
                    key=lambda item: str(item.get("knowledge_edge_id", "")),
                ),
            }
        )
    )


def classify_concerns(
    *,
    title: str,
    intent: str,
    task_class: str,
    read_scope: list[str],
    write_scope: list[str],
) -> tuple[str, ...]:
    text = " ".join([title, intent, task_class, *read_scope, *write_scope]).lower()
    found: set[str] = set()
    keywords = {
        "SECURITY": (
            "security",
            "secure",
            "authorization",
            "cve",
            "vulnerability",
            "threat",
            "secret",
            "permission",
        ),
        "AUTH": ("auth", "login", "identity", "oauth", "session"),
        "PAYMENTS": ("payment", "checkout", "settlement", "refund", "invoice"),
        "DATABASE": ("database", "sql", "postgres", "schema", "repository"),
        "MIGRATION": ("migration", "alembic", "upgrade", "downgrade"),
        "WEB_UI": ("frontend", "react", "web", "screen", "component", ".tsx", ".css"),
        "MOBILE_UI": ("android", "ios", "mobile", "flutter", "swift", "kotlin"),
        "DESIGN": ("design", "pxg", "visual", "layout", "token"),
        "ACCESSIBILITY": ("accessibility", "a11y", "wcag"),
        "BACKEND_API": ("api", "endpoint", "service", "gateway", "fastapi"),
        "TESTING": ("test", "pytest", "playwright", "verification", "oracle"),
        "PERFORMANCE": ("performance", "latency", "throughput", "benchmark"),
        "OBSERVABILITY": ("observability", "telemetry", "metric", "trace", "logging"),
        "DEPLOYMENT": ("deploy", "docker", "cloud", "release", "runtime"),
        "INCIDENT": ("incident", "outage", "recovery", "rollback"),
        "PACKAGE_UPGRADE": ("dependency", "package", "version", "upgrade"),
        "DONOR_REUSE": ("donor", "reuse", "template", "reference architecture"),
    }
    for concern, terms in keywords.items():
        if any(term in text for term in terms):
            found.add(concern)
    if task_class == "verification":
        found.add("TESTING")
    if not found:
        found.add("GENERIC_IMPLEMENTATION")
    return tuple(item for item in CONCERN_ORDER if item in found)


def route_policy(concern: str) -> dict[str, object]:
    try:
        return dict(_ROUTE_POLICIES[concern])
    except KeyError as exc:
        raise DdeError(
            "VEKL_ROUTE_UNKNOWN",
            "knowledge concern has no admitted deterministic route",
            details={"concern": concern},
        ) from exc


def route_slug(concern: str) -> str:
    return f"route.{concern.lower()}.v1"


def selection_role(
    *, resource_kind: str, activation_mode: str, purpose: str
) -> tuple[str, str]:
    if activation_mode in {
        "TOOL_EXECUTION",
        "PLUGIN_COMPONENT",
        "MCP_RUNTIME",
        "LSP_RUNTIME",
    }:
        role = "EXECUTOR"
    elif resource_kind in {"TEST_ORACLE"} or activation_mode == "TEST_ORACLE":
        role = "VERIFIER"
    elif resource_kind == "SECURITY_FEED" or activation_mode == "SECURITY_GATE":
        role = "SECURITY"
    elif resource_kind in {"ISSUE", "DISCUSSION", "FORUM_POST", "COMMUNITY_SIGNAL"}:
        role = "DIAGNOSTIC"
    elif resource_kind == "SKILL":
        role = "PROCEDURAL_SKILL"
    elif (
        resource_kind in {"TEMPLATE", "REPOSITORY"} and activation_mode == "DONOR_REUSE"
    ):
        role = "REUSE_CANDIDATE"
    elif resource_kind == "DEPLOYMENT_RECIPE" or activation_mode == "DEPLOYMENT_ACTION":
        role = "DEPLOYMENT"
    elif resource_kind == "OBSERVABILITY_INTEGRATION":
        role = "OBSERVABILITY"
    elif resource_kind in {"SPEC", "OFFICIAL_DOC"}:
        role = "NORMATIVE_REFERENCE"
    else:
        role = "IMPLEMENTATION_GUIDANCE"
    return purpose, role


@dataclass(frozen=True)
class ChallengeEligibility:
    eligible: bool
    reason: str


def challenge_eligibility(
    *,
    classification: str,
    source_trust: str,
    provenance_valid: bool,
    stale: bool,
    corroboration_count: int,
    deterministic_reproduction: bool,
) -> ChallengeEligibility:
    if classification != "TRUTH_CONFLICT_SIGNAL":
        return ChallengeEligibility(False, "NOT_TRUTH_CONFLICT")
    if not provenance_valid or stale:
        return ChallengeEligibility(False, "EVIDENCE_NOT_CURRENT_OR_PROVEN")
    if source_trust == "S8_UNTRUSTED":
        return ChallengeEligibility(False, "UNTRUSTED_SOURCE")
    if source_trust in {"S1_NORMATIVE", "S2_FIRST_PARTY"} or deterministic_reproduction:
        return ChallengeEligibility(True, "STRONG_EVIDENCE")
    if source_trust in {
        "S3_VERIFIED_REGISTRY",
        "S4_MAINTAINED_OSS",
        "S5_MAINTAINER_COMMUNITY",
    }:
        return ChallengeEligibility(
            corroboration_count >= 2,
            "CORROBORATION_REQUIRED" if corroboration_count < 2 else "CORROBORATED",
        )
    return ChallengeEligibility(False, "DISCOVERY_ONLY")


def validate_truth_patch(proposal: dict[str, object]) -> str:
    kind = proposal.get("truth_change_kind")
    allowed = {
        "PRODUCT_CONSTITUTION_REVISION",
        "REQUIREMENT_ADD",
        "REQUIREMENT_AMEND",
        "REQUIREMENT_RETIRE",
        "EDR_ADD",
        "EDR_SUPERSEDE",
    }
    if kind not in allowed:
        raise DdeError(
            "VEKL_TRUTH_PATCH_INVALID",
            "truth challenge patch kind is not an admitted governed mutation",
            details={"truth_change_kind": kind},
        )
    if kind == "EDR_AMEND":
        raise DdeError(
            "VEKL_TRUTH_PATCH_INVALID",
            "accepted EDRs are immutable and must be superseded",
        )
    if not proposal.get("exact_truth_patch"):
        raise DdeError(
            "VEKL_TRUTH_PATCH_INVALID", "truth challenge requires an exact truth patch"
        )
    if not proposal.get("verification_plan"):
        raise DdeError(
            "VEKL_TRUTH_PATCH_INVALID", "truth challenge requires a verification plan"
        )
    return str(kind)


def resolution_envelope(
    *,
    graph_hash: str,
    context_index_id: UUID | None,
    context_index_version: str | None,
    embedding_model_version: str,
) -> dict[str, object]:
    return {
        "concern_classifier_id": "dde.vekl.concern_classifier",
        "concern_classifier_version": CONCERN_CLASSIFIER_VERSION,
        "retrieval_route_registry_version": ROUTE_REGISTRY_VERSION,
        "retrieval_route_policy_hash": RETRIEVAL_ROUTE_POLICY_HASH,
        "graph_compiler_version": GRAPH_COMPILER_VERSION,
        "graph_snapshot_hash": graph_hash,
        "chunking_algorithm_version": CHUNKING_ALGORITHM_VERSION,
        "embedding_model_version": embedding_model_version,
        "context_index_id": None if context_index_id is None else str(context_index_id),
        "context_index_version": context_index_version,
        "lexical_retriever_version": LEXICAL_RETRIEVER_VERSION,
        "hybrid_ranker_version": HYBRID_RANKER_VERSION,
        "ranking_weights_hash": RANKING_WEIGHTS_HASH,
        "hard_eligibility_policy_hash": ELIGIBILITY_POLICY_HASH,
        "stable_tie_break_rule": STABLE_TIE_BREAK_RULE,
        "resource_outcome_policy_version": RESOURCE_OUTCOME_POLICY_VERSION,
    }
