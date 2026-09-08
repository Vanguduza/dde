"""Fail-closed VEKL eligibility before deterministic ranking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from engine.contracts.task_signature import TaskSignature
from engine.contracts.vekl_resource import VEKLResource
from engine.core.errors import DdeError

APPLICATION_MANUFACTURING_VEKL = "APPLICATION_MANUFACTURING_VEKL"
VEKL_SCOPE_VIOLATION = "VEKL_SCOPE_VIOLATION"
EXECUTION_MODES = frozenset(
    {
        "TOOL_EXECUTION",
        "PLUGIN_COMPONENT",
        "MCP_RUNTIME",
        "LSP_RUNTIME",
        "HOOK_ENFORCEMENT",
        "LOOP_EXECUTION",
        "TEST_ORACLE",
        "SECURITY_GATE",
        "DEPLOYMENT_ACTION",
    }
)
REFERENCE_STATES = frozenset(
    {
        "REFERENCE_QUALIFIED",
        "EXECUTION_QUARANTINED",
        "EXECUTION_EVALUATED",
        "CANARY",
        "PRODUCTION_QUALIFIED",
    }
)
EXECUTION_STATES = frozenset({"EXECUTION_EVALUATED", "CANARY", "PRODUCTION_QUALIFIED"})
TRUST_RANK = {
    "S1_NORMATIVE": 8,
    "S2_FIRST_PARTY": 7,
    "S3_VERIFIED_REGISTRY": 6,
    "S4_MAINTAINED_OSS": 5,
    "S5_MAINTAINER_COMMUNITY": 4,
    "S6_COMMUNITY_CORROBORATED": 3,
    "S7_DISCOVERY_ONLY": 2,
    "S8_UNTRUSTED": 1,
}


@dataclass(frozen=True)
class EligibilityContext:
    project_kind: str
    request_mode: str
    truth_constraints: dict[str, object]
    admitted_source_ids: frozenset[str]
    available_capabilities: frozenset[str]
    available_verifiers: frozenset[str]
    sandbox_available: bool
    offline: bool = False
    now: datetime = datetime.min.replace(tzinfo=UTC)


@dataclass(frozen=True)
class EligibilityDecision:
    resource: VEKLResource
    activation_mode: str
    eligible: bool
    reasons: tuple[str, ...]
    score: tuple[int, int, int, int]


def enforce_target_scope(*, project_kind: str, request_mode: str) -> None:
    if request_mode != APPLICATION_MANUFACTURING_VEKL:
        raise DdeError(
            VEKL_SCOPE_VIOLATION,
            "Production VEKL accepts only application-manufacturing requests",
            details={"project_kind": project_kind, "request_mode": request_mode},
        )
    if project_kind != "TARGET_APPLICATION":
        raise DdeError(
            VEKL_SCOPE_VIOLATION,
            "Production VEKL cannot resolve resources for the DDE control plane",
            details={"project_kind": project_kind, "request_mode": request_mode},
        )


def _subset(required: list[str], allowed: list[str] | None) -> bool:
    return set(required).issubset(set(allowed or []))


def _version_matches(required: str, observed: object) -> bool:
    actual = str(observed)
    if required.endswith(".x"):
        return actual.split(".", 1)[0] == required.split(".", 1)[0]
    return actual == required


def _budget_value(values: dict[str, object], key: str) -> int:
    value = values.get(key, 0)
    return int(value) if isinstance(value, (int, float)) else 0


def _stack_value_matches(expected: object, actual: object) -> bool:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(
            key in actual and _stack_value_matches(value, actual[key])
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        if isinstance(actual, list):
            return any(item in expected for item in actual)
        return actual in expected
    return actual == expected


def evaluate(
    resource: VEKLResource,
    *,
    activation_mode: str,
    signature: TaskSignature,
    context: EligibilityContext,
) -> EligibilityDecision:
    reasons: list[str] = []
    executable = activation_mode in EXECUTION_MODES
    if activation_mode not in resource.activation_modes:
        reasons.append("ACTIVATION_MODE_UNQUALIFIED")
    if resource.lifecycle_state in {"REVOKED", "DEPRECATED"}:
        reasons.append("RESOURCE_REVOKED")
    elif resource.lifecycle_state not in (
        EXECUTION_STATES if executable else REFERENCE_STATES
    ):
        reasons.append(
            "EXECUTABLE_NOT_QUALIFIED" if executable else "REFERENCE_NOT_QUALIFIED"
        )
    if (
        resource.source_id is not None
        and str(resource.source_id) not in context.admitted_source_ids
    ):
        reasons.append("SOURCE_NOT_ADMITTED")
    if resource.source_uri and not bool(resource.provenance.get("egress_admitted")):
        reasons.append("HOST_NOT_ADMITTED")
    if resource.source_trust == "S8_UNTRUSTED":
        reasons.append("SOURCE_UNTRUSTED")
    if (
        resource.source_trust == "S7_DISCOVERY_ONLY"
        and activation_mode != "DISCOVERY_ONLY"
    ):
        reasons.append("DISCOVERY_ONLY_SOURCE")
    if activation_mode in {
        "DONOR_REUSE",
        *EXECUTION_MODES,
    } and resource.reuse_class not in {
        "OPEN_REUSE",
        "CONDITIONAL_REUSE",
    }:
        reasons.append("REUSE_CLASS_INCOMPATIBLE")
    if not resource.license_ids or resource.reuse_class in {
        "UNKNOWN",
        "REJECTED",
        "RESTRICTED",
    }:
        reasons.append("LICENSE_OR_PROVENANCE_INSUFFICIENT")
    if not resource.provenance.get("source") or not resource.provenance.get(
        "hash_verified"
    ):
        reasons.append("LICENSE_OR_PROVENANCE_INSUFFICIENT")
    versions = signature.constraints.get("versions", {})
    if not isinstance(versions, dict):
        versions = {}
    if any(
        key not in versions or not _version_matches(required, versions[key])
        for key, required in resource.exact_versions.items()
    ):
        reasons.append("VERSION_INCOMPATIBLE")
    stack = signature.constraints.get("stack", {})
    if not isinstance(stack, dict):
        stack = {}
    if any(
        key not in stack or not _stack_value_matches(expected, stack[key])
        for key, expected in resource.stack_constraints.items()
    ):
        reasons.append("STACK_INCOMPATIBLE")
    for key, expected in resource.truth_constraints.items():
        if (
            key in context.truth_constraints
            and context.truth_constraints[key] != expected
        ):
            reasons.append("PROJECT_TRUTH_CONFLICT")
            break
    if resource.injection_findings:
        reasons.append("PROMPT_INJECTION_DETECTED")
    if executable and not resource.component_kind:
        reasons.append("BUNDLE_EXECUTION_FORBIDDEN")
    if executable and not context.sandbox_available:
        reasons.append("SANDBOX_UNAVAILABLE")
    if not set(resource.required_capabilities).issubset(context.available_capabilities):
        reasons.append("CAPABILITY_UNAVAILABLE")
    if not set(resource.required_verifiers).issubset(context.available_verifiers):
        reasons.append("VERIFIER_UNAVAILABLE")
    if not _subset(resource.filesystem_scopes, signature.allowed_filesystem_scopes):
        reasons.append("FILESYSTEM_SCOPE_EXCESSIVE")
    if not _subset(resource.network_scopes, signature.allowed_network_scopes):
        reasons.append("NETWORK_SCOPE_EXCESSIVE")
    if not _subset(resource.secret_scopes, signature.allowed_secret_scopes):
        reasons.append("SECRET_SCOPE_EXCESSIVE")
    if _budget_value(resource.budget, "tokens") > _budget_value(
        signature.budget, "tokens"
    ):
        reasons.append("RESERVED_BUDGET_INSUFFICIENT")
    stale = bool(resource.freshness.get("stale"))
    if stale and (
        resource.resource_kind == "SECURITY_FEED"
        or bool(resource.freshness.get("mandatory"))
    ):
        reasons.append("MANDATORY_SECURITY_EVIDENCE_STALE")
    if context.offline and (
        not resource.exact_versions
        or not bool(resource.provenance.get("offline_pin_available"))
    ):
        reasons.append("OFFLINE_EXACT_PIN_REQUIRED")
    unique_reasons = tuple(dict.fromkeys(reasons))
    exact_score = len(resource.exact_versions)
    task_specificity = len(resource.truth_constraints)
    freshness_score = 0 if stale else 1
    return EligibilityDecision(
        resource=resource,
        activation_mode=activation_mode,
        eligible=not unique_reasons,
        reasons=unique_reasons,
        score=(
            exact_score,
            TRUST_RANK[resource.source_trust],
            task_specificity,
            freshness_score,
        ),
    )


def rank_eligible(decisions: list[EligibilityDecision]) -> list[EligibilityDecision]:
    if any(not decision.eligible for decision in decisions):
        raise ValueError("ranking may only receive hard-eligible resources")
    return sorted(
        decisions,
        key=lambda item: (item.score, str(item.resource.resource_id)),
        reverse=True,
    )
