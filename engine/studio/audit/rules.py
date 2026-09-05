"""Deterministic DDE-069 Screen Audit reconciliation rules.

This module is deliberately pure. It compares the already-authoritative
Frontend Contract and PXG and emits audit drafts; it never writes project
truth and never asks a model to decide deterministic completeness facts.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, Literal

from engine.contracts.frontend_contract import FrontendContract, Obligation
from engine.studio.coverage.thinness import detect as detect_thinness
from engine.studio.pxg.service import PxgGraph

AssessmentState = Literal[
    "PASS", "FAIL", "PARTIAL", "UNKNOWN", "BLOCKED", "NOT_APPLICABLE"
]
AuditDimension = Literal[
    "CONTRACT",
    "JOURNEY",
    "FUNCTIONAL",
    "STATE",
    "DATA",
    "ROLE",
    "PERMISSION",
    "NAVIGATION",
    "ACCESSIBILITY",
    "RESPONSIVE_PLATFORM",
    "VISUAL",
    "SOURCE_PROVENANCE",
    "SECURITY",
    "VERIFICATION",
    "DRIFT",
]
Severity = Literal["BLOCKING", "ERROR", "WARNING", "INFO"]

POLICY_VERSION: Final = "screen-audit-v1"
MANDATORY_VISUAL_KINDS: Final[frozenset[str]] = frozenset(
    {"silhouette", "visual_critique"}
)
ALL_DIMENSIONS: Final[tuple[AuditDimension, ...]] = (
    "CONTRACT",
    "JOURNEY",
    "FUNCTIONAL",
    "STATE",
    "DATA",
    "ROLE",
    "PERMISSION",
    "NAVIGATION",
    "ACCESSIBILITY",
    "RESPONSIVE_PLATFORM",
    "VISUAL",
    "SOURCE_PROVENANCE",
    "SECURITY",
    "VERIFICATION",
    "DRIFT",
)
DIMENSION_MAP: Final[dict[str, AuditDimension]] = {
    "screen": "CONTRACT",
    "journey": "JOURNEY",
    "component": "FUNCTIONAL",
    "interaction": "FUNCTIONAL",
    "state": "STATE",
    "data_state": "DATA",
    "responsive": "RESPONSIVE_PLATFORM",
    "accessibility": "ACCESSIBILITY",
    "navigation": "NAVIGATION",
    "verification": "VERIFICATION",
}


@dataclass(frozen=True)
class AuditEvidenceDraft:
    key: str
    dimension: AuditDimension
    evidence_kind: str
    source_type: str
    source_ref: str
    assessment_state: AssessmentState
    pxg_key: str | None = None
    source_revision: str | None = None
    content_hash: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class AuditFindingDraft:
    finding_type: str
    dimension: AuditDimension
    severity: Severity
    assessment_state: AssessmentState
    message: str
    rule_id: str
    pxg_key: str | None = None
    node_key: str | None = None
    evidence_keys: tuple[str, ...] = ()
    requirement_refs: tuple[str, ...] = ()
    journey_refs: tuple[str, ...] = ()
    role_refs: tuple[str, ...] = ()
    dependency_keys: tuple[str, ...] = ()
    decision_ref: str | None = None


@dataclass(frozen=True)
class AuditScreenDraft:
    pxg_key: str
    screen_kind: str
    platform: str
    module_or_product_area: str | None
    route_identity: str | None
    source_refs: tuple[dict[str, object], ...]
    journey_refs: tuple[str, ...]
    role_refs: tuple[str, ...]
    feature_requirement_refs: tuple[str, ...]
    data_dependency_refs: tuple[str, ...]
    verification_binding_refs: tuple[str, ...]
    render_evidence_refs: tuple[str, ...]
    implementation_state: Literal["PRESENT", "MISSING", "ORPHANED", "UNKNOWN"]
    assessment_state: AssessmentState
    dimension_states: dict[str, str]


@dataclass(frozen=True)
class AuditComputation:
    screens: tuple[AuditScreenDraft, ...]
    findings: tuple[AuditFindingDraft, ...]
    evidence: tuple[AuditEvidenceDraft, ...]
    summary_state: AssessmentState


def _screen_root(graph: PxgGraph, key: str, screen_keys: frozenset[str]) -> str:
    node = graph.node_by_key(key)
    seen: set[str] = set()
    while node is not None and node.pxg_key not in seen:
        seen.add(node.pxg_key)
        if node.node_kind == "screen":
            return node.pxg_key
        node = graph.node_by_key(node.parent_key) if node.parent_key else None
    prefix_matches = [
        screen
        for screen in screen_keys
        if key == screen or key.startswith(screen + "#") or key.startswith(screen + "/")
    ]
    if prefix_matches:
        return max(prefix_matches, key=len)
    if "#" in key:
        return key.split("#", 1)[0]
    return key


def _state_for(states: Mapping[str, str]) -> AssessmentState:
    values = tuple(states.values())
    if not values or all(value == "NOT_APPLICABLE" for value in values):
        return "NOT_APPLICABLE"
    if "BLOCKED" in values:
        return "BLOCKED"
    if "FAIL" in values:
        return "FAIL"
    if "PARTIAL" in values:
        return "PARTIAL"
    if "UNKNOWN" in values:
        return "PARTIAL" if "PASS" in values else "UNKNOWN"
    return "PASS"


def _missing_type(obligation: Obligation) -> tuple[str, Severity]:
    mapping: dict[str, tuple[str, Severity]] = {
        "screen": ("REQUIRED_SCREEN_MISSING", "BLOCKING"),
        "journey": ("REQUIRED_JOURNEY_MISSING", "BLOCKING"),
        "component": ("REQUIRED_COMPONENT_MISSING", "ERROR"),
        "interaction": ("REQUIRED_INTERACTION_MISSING", "ERROR"),
        "state": ("REQUIRED_STATE_MISSING", "BLOCKING"),
        "data_state": ("REQUIRED_DATA_STATE_MISSING", "ERROR"),
        "responsive": ("PLATFORM_VARIANT_MISSING", "ERROR"),
        "accessibility": ("ACCESSIBILITY_OBLIGATION_MISSING", "ERROR"),
        "navigation": ("MISSING_NAVIGATION_TARGET", "ERROR"),
        "verification": ("VERIFICATION_BINDING_MISSING", "BLOCKING"),
    }
    return mapping[obligation.dimension]


def _str_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def reconcile(
    contract: FrontendContract | None,
    graph: PxgGraph,
    *,
    passing_verifications: Mapping[str, frozenset[str]] | None = None,
    affected_keys: frozenset[str] | None = None,
) -> AuditComputation:
    """Reconcile required vs implemented screen experience deterministically.

    `passing_verifications` contains only evidence already accepted as current by
    DDE verification. Absence means UNKNOWN, never PASS. `affected_keys` limits
    emitted screen records for incremental runs but does not change rule meaning.
    """
    passed = passing_verifications or {}
    obligations = tuple(contract.obligations) if contract else ()
    screen_obligations = tuple(
        item for item in obligations if item.dimension == "screen"
    )
    actual_screens = {
        node.pxg_key: node for node in graph.nodes if node.node_kind == "screen"
    }
    declared_screen_keys = frozenset(item.pxg_key for item in screen_obligations)
    all_screen_keys = frozenset(actual_screens) | declared_screen_keys

    findings: list[AuditFindingDraft] = []
    evidence: list[AuditEvidenceDraft] = []
    states: dict[str, dict[str, str]] = {
        key: {dimension: "UNKNOWN" for dimension in ALL_DIMENSIONS}
        for key in all_screen_keys
    }
    requirement_refs: dict[str, set[str]] = {key: set() for key in all_screen_keys}
    journey_refs: dict[str, set[str]] = {key: set() for key in all_screen_keys}

    if contract is None:
        findings.append(
            AuditFindingDraft(
                finding_type="FRONTEND_CONTRACT_UNAVAILABLE",
                dimension="CONTRACT",
                severity="BLOCKING",
                assessment_state="BLOCKED",
                message=(
                    "No active Frontend Contract exists; required-vs-actual audit "
                    "is blocked, not zero coverage."
                ),
                rule_id="contract.available",
                dependency_keys=("contract:active",),
            )
        )
        for key in states:
            states[key]["CONTRACT"] = "BLOCKED"
    else:
        evidence.append(
            AuditEvidenceDraft(
                key=f"contract:{contract.contract_id}:{contract.contract_version}",
                dimension="CONTRACT",
                evidence_kind="CONTRACT_VERSION",
                source_type="FrontendContract",
                source_ref=str(contract.contract_id),
                content_hash=contract.content_hash,
                assessment_state="PASS",
                metadata={"contract_version": contract.contract_version},
            )
        )

    for key, node in actual_screens.items():
        evidence.append(
            AuditEvidenceDraft(
                key=f"pxg:{graph.revision}:{key}",
                dimension="CONTRACT",
                evidence_kind="PXG_NODE",
                source_type="PXG",
                source_ref=key,
                pxg_key=key,
                assessment_state="PASS",
                metadata={"pxg_revision": graph.revision, "node_kind": node.node_kind},
            )
        )
        states[key]["DRIFT"] = "PASS"
        if node.source_refs:
            states[key]["SOURCE_PROVENANCE"] = "PASS"
        else:
            states[key]["SOURCE_PROVENANCE"] = "UNKNOWN"
            findings.append(
                AuditFindingDraft(
                    finding_type="SOURCE_PROVENANCE_UNKNOWN",
                    dimension="SOURCE_PROVENANCE",
                    severity="WARNING",
                    assessment_state="UNKNOWN",
                    message=(
                        "Screen has no source reference in PXG; provenance is "
                        "unknown rather than inferred."
                    ),
                    rule_id="source.known",
                    pxg_key=key,
                    dependency_keys=(key, "source:provenance"),
                    evidence_keys=(f"pxg:{graph.revision}:{key}",),
                )
            )

        bound_kinds = frozenset(
            _str_tuple(node.attributes.get("bound_verification_kinds"))
        )
        current_kinds = passed.get(key, frozenset())
        missing_bindings = sorted(MANDATORY_VISUAL_KINDS - bound_kinds)
        if missing_bindings:
            states[key]["VERIFICATION"] = "FAIL"
            states[key]["VISUAL"] = "FAIL"
            findings.append(
                AuditFindingDraft(
                    finding_type="MANDATORY_VISUAL_BINDING_MISSING",
                    dimension="VERIFICATION",
                    severity="BLOCKING",
                    assessment_state="FAIL",
                    message=(
                        "Screen is missing mandatory DDE-068 bindings: "
                        + ", ".join(missing_bindings)
                        + "."
                    ),
                    rule_id="verification.mandatory_visual_bound",
                    pxg_key=key,
                    dependency_keys=(key, "verification:binding"),
                    evidence_keys=(f"pxg:{graph.revision}:{key}",),
                )
            )
        else:
            missing_current = sorted(MANDATORY_VISUAL_KINDS - current_kinds)
            if missing_current:
                states[key]["VERIFICATION"] = "UNKNOWN"
                states[key]["VISUAL"] = "UNKNOWN"
                findings.append(
                    AuditFindingDraft(
                        finding_type="MANDATORY_VISUAL_VERIFICATION_NOT_CURRENT",
                        dimension="VISUAL",
                        severity="BLOCKING",
                        assessment_state="UNKNOWN",
                        message=(
                            "Screen lacks current accepted passing DDE-068 "
                            "evidence for: " + ", ".join(missing_current) + "."
                        ),
                        rule_id="verification.mandatory_visual_current",
                        pxg_key=key,
                        dependency_keys=(key, "verification:current"),
                        evidence_keys=(f"pxg:{graph.revision}:{key}",),
                    )
                )
            else:
                states[key]["VISUAL"] = "PASS"
                states[key]["VERIFICATION"] = (
                    "PASS" if bound_kinds.issubset(current_kinds) else "UNKNOWN"
                )

    for obligation in obligations:
        screen_key = _screen_root(
            graph, obligation.pxg_key, declared_screen_keys | frozenset(actual_screens)
        )
        if screen_key not in states:
            states[screen_key] = {dimension: "UNKNOWN" for dimension in ALL_DIMENSIONS}
            requirement_refs[screen_key] = set()
            journey_refs[screen_key] = set()
        requirement_refs[screen_key].update(obligation.requirement_refs)
        if obligation.dimension == "journey":
            journey_refs[screen_key].add(obligation.pxg_key)
        audit_dimension = DIMENSION_MAP[obligation.dimension]
        evidence_key = f"obligation:{obligation.obligation_id}"
        evidence.append(
            AuditEvidenceDraft(
                key=evidence_key,
                dimension=audit_dimension,
                evidence_kind="CONTRACT_OBLIGATION",
                source_type="FrontendContract",
                source_ref=str(obligation.obligation_id),
                pxg_key=screen_key,
                assessment_state="UNKNOWN",
                metadata={
                    "dimension": obligation.dimension,
                    "applicability": obligation.applicability,
                    "target_key": obligation.pxg_key,
                },
            )
        )

        if obligation.applicability in {"DEFERRED_APPROVED", "NOT_APPLICABLE_APPROVED"}:
            if not obligation.applicability_decision_ref:
                states[screen_key][audit_dimension] = "FAIL"
                findings.append(
                    AuditFindingDraft(
                        finding_type="DEFERRED_WITHOUT_DECISION",
                        dimension=audit_dimension,
                        severity="BLOCKING",
                        assessment_state="FAIL",
                        message=(
                            f"{obligation.pxg_key} is omitted by "
                            f"{obligation.applicability} without a durable "
                            "decision reference."
                        ),
                        rule_id="contract.no_silent_omission",
                        pxg_key=screen_key,
                        evidence_keys=(evidence_key,),
                        requirement_refs=tuple(obligation.requirement_refs),
                        dependency_keys=(obligation.pxg_key, "contract:active"),
                    )
                )
            elif states[screen_key][audit_dimension] == "UNKNOWN":
                states[screen_key][audit_dimension] = "NOT_APPLICABLE"
            continue
        if obligation.applicability == "BLOCKED_RECORDED":
            states[screen_key][audit_dimension] = "BLOCKED"
            continue

        target = graph.node_by_key(obligation.pxg_key)
        if target is None:
            finding_type, severity = _missing_type(obligation)
            states[screen_key][audit_dimension] = "FAIL"
            findings.append(
                AuditFindingDraft(
                    finding_type=finding_type,
                    dimension=audit_dimension,
                    severity=severity,
                    assessment_state="FAIL",
                    message=(
                        f"Required {obligation.dimension} {obligation.pxg_key!r} "
                        f"is absent from PXG revision {graph.revision}."
                    ),
                    rule_id=f"obligation.{obligation.dimension}.exists",
                    pxg_key=screen_key,
                    evidence_keys=(evidence_key,),
                    requirement_refs=tuple(obligation.requirement_refs),
                    dependency_keys=(obligation.pxg_key, "contract:active"),
                )
            )
            continue

        if states[screen_key][audit_dimension] not in {"FAIL", "BLOCKED"}:
            states[screen_key][audit_dimension] = "PASS"
        required_kinds = frozenset(obligation.verification_kinds)
        if required_kinds:
            current = passed.get(obligation.pxg_key, frozenset())
            missing = sorted(required_kinds - current)
            if missing:
                states[screen_key]["VERIFICATION"] = "UNKNOWN"
                findings.append(
                    AuditFindingDraft(
                        finding_type="REQUIRED_VERIFICATION_NOT_CURRENT",
                        dimension="VERIFICATION",
                        severity="BLOCKING",
                        assessment_state="UNKNOWN",
                        message=(
                            f"{obligation.pxg_key!r} lacks current passing "
                            f"evidence for: {', '.join(missing)}."
                        ),
                        rule_id="verification.current",
                        pxg_key=screen_key,
                        evidence_keys=(evidence_key,),
                        requirement_refs=tuple(obligation.requirement_refs),
                        dependency_keys=(obligation.pxg_key, "verification:current"),
                    )
                )
            elif states[screen_key]["VERIFICATION"] != "FAIL":
                states[screen_key]["VERIFICATION"] = "PASS"

    assessable_screen_keys = {
        item.pxg_key
        for item in screen_obligations
        if item.applicability in {"REQUIRED", "OPTIONAL_SELECTED"}
    }
    for key in actual_screens:
        if contract is None:
            continue
        if key not in assessable_screen_keys:
            states[key]["CONTRACT"] = "PARTIAL"
            findings.append(
                AuditFindingDraft(
                    finding_type="SCREEN_WITHOUT_PRODUCT_OBLIGATION",
                    dimension="CONTRACT",
                    severity="WARNING",
                    assessment_state="PARTIAL",
                    message=(
                        "Implemented screen has no selected/required screen "
                        "obligation in the active Frontend Contract."
                    ),
                    rule_id="contract.screen_declared",
                    pxg_key=key,
                    evidence_keys=(f"pxg:{graph.revision}:{key}",),
                    dependency_keys=(key, "contract:active"),
                )
            )
        elif states[key]["CONTRACT"] == "UNKNOWN":
            states[key]["CONTRACT"] = "PASS"

    for node in graph.orphan_nodes():
        screen_key = _screen_root(graph, node.pxg_key, frozenset(states))
        if screen_key in states:
            states[screen_key]["DRIFT"] = "FAIL"
        findings.append(
            AuditFindingDraft(
                finding_type="ORPHAN_NODE",
                dimension="DRIFT",
                severity="ERROR",
                assessment_state="FAIL",
                message=(
                    f"PXG node {node.pxg_key!r} names missing parent "
                    f"{node.parent_key!r}."
                ),
                rule_id="pxg.parent_exists",
                pxg_key=screen_key,
                node_key=node.pxg_key,
                dependency_keys=(node.pxg_key, node.parent_key or ""),
            )
        )
    for edge in graph.dangling_edges():
        screen_key = _screen_root(graph, edge.from_key, frozenset(states))
        if screen_key in states:
            states[screen_key]["NAVIGATION"] = "FAIL"
            states[screen_key]["DRIFT"] = "FAIL"
        findings.append(
            AuditFindingDraft(
                finding_type="DANGLING_NAVIGATION_TARGET",
                dimension="NAVIGATION",
                severity="ERROR",
                assessment_state="FAIL",
                message=(
                    f"PXG edge {edge.from_key!r} → {edge.to_key!r} targets a "
                    "missing node."
                ),
                rule_id="navigation.target_exists",
                pxg_key=screen_key,
                node_key=edge.from_key,
                dependency_keys=(edge.from_key, edge.to_key),
            )
        )

    for journey in graph.nodes_of_kind("journey"):
        outgoing = tuple(
            edge for edge in graph.edges if edge.from_key == journey.pxg_key
        )
        if not outgoing:
            screen_key = _screen_root(graph, journey.pxg_key, frozenset(states))
            if screen_key in states:
                states[screen_key]["JOURNEY"] = "FAIL"
            findings.append(
                AuditFindingDraft(
                    finding_type="JOURNEY_DEAD_END",
                    dimension="JOURNEY",
                    severity="ERROR",
                    assessment_state="FAIL",
                    message=(
                        f"Journey {journey.pxg_key!r} has no outgoing PXG transition."
                    ),
                    rule_id="journey.has_exit",
                    pxg_key=screen_key if screen_key in states else None,
                    node_key=journey.pxg_key,
                    journey_refs=(journey.pxg_key,),
                    dependency_keys=(journey.pxg_key,),
                )
            )

    for thin in detect_thinness(graph):
        screen_key = _screen_root(graph, thin.pxg_key, frozenset(states))
        dimension: AuditDimension
        thin_finding_type: str
        thin_severity: Severity
        if thin.dimension == "interaction":
            dimension = "FUNCTIONAL"
            if "destructive" in thin.detail:
                thin_finding_type = "DESTRUCTIVE_ACTION_NO_CONFIRMATION"
                thin_severity = "BLOCKING"
            else:
                thin_finding_type = "VISIBLE_CONTROL_UNBOUND"
                thin_severity = "ERROR"
        elif thin.dimension == "data_state":
            dimension = "STATE"
            thin_finding_type = "MANDATORY_DATA_STATE_MISSING"
            thin_severity = "ERROR"
        elif thin.dimension == "responsive":
            dimension = "RESPONSIVE_PLATFORM"
            thin_finding_type = "PLATFORM_VARIANT_MISSING"
            thin_severity = "ERROR"
        else:
            dimension = "FUNCTIONAL"
            thin_finding_type = "SCREEN_IMPLEMENTATION_THIN"
            thin_severity = "WARNING"
        if screen_key in states:
            states[screen_key][dimension] = "FAIL"
        findings.append(
            AuditFindingDraft(
                finding_type=thin_finding_type,
                dimension=dimension,
                severity=thin_severity,
                assessment_state="FAIL",
                message=thin.detail,
                rule_id=f"coverage.thinness.{thin.dimension}",
                pxg_key=screen_key if screen_key in states else None,
                node_key=thin.pxg_key if thin.pxg_key != screen_key else None,
                dependency_keys=(thin.pxg_key,),
            )
        )

    screens: list[AuditScreenDraft] = []
    for key in sorted(states):
        if affected_keys is not None and not any(
            dep == key or dep.startswith(key + "#") or dep.startswith(key + "/")
            for dep in affected_keys
        ):
            continue
        screen_node = actual_screens.get(key)
        screen_states = states[key]
        implementation_state: Literal["PRESENT", "MISSING", "ORPHANED", "UNKNOWN"] = (
            "PRESENT" if screen_node else "MISSING"
        )
        attrs = screen_node.attributes if screen_node else {}
        screens.append(
            AuditScreenDraft(
                pxg_key=key,
                screen_kind=screen_node.node_kind if screen_node else "screen",
                platform=str(attrs.get("platform") or "UNKNOWN"),
                module_or_product_area=(
                    str(attrs["module_or_product_area"])
                    if attrs.get("module_or_product_area")
                    else None
                ),
                route_identity=str(attrs["route"]) if attrs.get("route") else None,
                source_refs=tuple(
                    ref.model_dump(mode="json") for ref in screen_node.source_refs
                )
                if screen_node
                else (),
                journey_refs=tuple(sorted(journey_refs.get(key, set()))),
                role_refs=_str_tuple(attrs.get("role_refs")) if screen_node else (),
                feature_requirement_refs=tuple(
                    sorted(requirement_refs.get(key, set()))
                ),
                data_dependency_refs=(
                    _str_tuple(attrs.get("data_dependency_refs")) if screen_node else ()
                ),
                verification_binding_refs=(
                    _str_tuple(attrs.get("bound_verification_kinds"))
                    if screen_node
                    else ()
                ),
                render_evidence_refs=(),
                implementation_state=implementation_state,
                assessment_state=_state_for(screen_states),
                dimension_states=dict(screen_states),
            )
        )

    scoped_findings = findings
    scoped_evidence = evidence
    if affected_keys is not None:

        def relevant(key: str | None, dependencies: tuple[str, ...]) -> bool:
            if key and key in {screen.pxg_key for screen in screens}:
                return True
            return any(dep in affected_keys for dep in dependencies)

        scoped_findings = [
            item for item in findings if relevant(item.pxg_key, item.dependency_keys)
        ]
        used_evidence = {key for item in scoped_findings for key in item.evidence_keys}
        scoped_evidence = [
            item
            for item in evidence
            if item.key in used_evidence
            or item.pxg_key in {screen.pxg_key for screen in screens}
        ]

    summary = _state_for(
        {screen.pxg_key: screen.assessment_state for screen in screens}
    )
    if contract is None:
        summary = "BLOCKED"
    return AuditComputation(
        screens=tuple(screens),
        findings=tuple(scoped_findings),
        evidence=tuple(scoped_evidence),
        summary_state=summary,
    )
