"""Fail-closed Design System Compiler admission logic for M8 source artifacts."""

from __future__ import annotations

from dataclasses import dataclass

from engine.contracts.design_source_artifact import DesignSourceArtifact

COMPILER_VERSION = "m8.compiler.v1"
_CODE_KINDS = {"COMPONENT", "TEMPLATE", "THEME", "FOUNDATION"}


@dataclass(frozen=True)
class AdmissionDecision:
    framework_state: str
    license_state: str
    dependency_state: str
    security_state: str
    accessibility_state: str
    design_system_state: str
    token_mapping_report: dict[str, object]
    unsupported_behaviors: tuple[str, ...]
    hard_failures: tuple[str, ...]
    validation_obligations: tuple[str, ...]
    state: str


def evaluate_artifact(
    artifact: DesignSourceArtifact,
    *,
    project_frameworks: tuple[str, ...] = (),
    allow_conditional_license: bool = False,
) -> AdmissionDecision:
    hard: list[str] = []
    obligations: list[str] = []
    unsupported_raw = artifact.metadata.get("unsupported_behaviors", [])
    unsupported = (
        tuple(str(v) for v in unsupported_raw if isinstance(v, str))
        if isinstance(unsupported_raw, list)
        else ()
    )
    code_kind = artifact.artifact_kind in _CODE_KINDS

    if artifact.license_state == "OPEN_REUSE":
        license_state = "PASS"
    elif artifact.license_state == "CONDITIONAL_REUSE":
        license_state = "CONDITIONAL"
        if allow_conditional_license:
            obligations.append("CONDITIONAL_LICENSE_DECISION_REQUIRED_AT_PROMOTION")
        else:
            hard.append("LICENSE_CONDITIONAL_REQUIRES_EXPLICIT_DECISION")
    elif artifact.license_state == "REFERENCE_ONLY":
        license_state = "PASS"
        obligations.append("REFERENCE_ONLY_NO_CODE_REUSE")
    else:
        license_state = "FAIL"
        hard.append(f"LICENSE_{artifact.license_state}")

    if not code_kind:
        framework_state = "PASS"
    elif artifact.framework is None:
        framework_state = "UNKNOWN"
        hard.append("FRAMEWORK_UNKNOWN")
    elif project_frameworks and artifact.framework not in project_frameworks:
        framework_state = "FAIL"
        hard.append(f"FRAMEWORK_INCOMPATIBLE:{artifact.framework}")
    else:
        framework_state = "PASS"

    remote_runtime = tuple(
        dep
        for dep in artifact.dependency_manifest
        if dep.startswith("http://") or dep.startswith("https://")
    )
    if remote_runtime:
        dependency_state = "FAIL"
        hard.extend(f"HIDDEN_REMOTE_RUNTIME:{dep}" for dep in remote_runtime)
    else:
        dependency_state = "PASS"

    security_state = artifact.security_state
    if code_kind and security_state == "FAIL":
        hard.append("SECURITY_FAILED")
    elif code_kind and security_state == "UNKNOWN":
        hard.append("SECURITY_NOT_EVALUATED")

    accessibility_state = artifact.accessibility_state
    if code_kind and accessibility_state == "FAIL":
        hard.append("ACCESSIBILITY_FAILED")
    elif code_kind and accessibility_state in {"UNKNOWN", "PARTIAL"}:
        hard.append("ACCESSIBILITY_INCOMPLETE")

    if code_kind and artifact.compatibility_state == "FAIL":
        hard.append("PROJECT_COMPATIBILITY_FAILED")
    elif code_kind and artifact.compatibility_state == "UNKNOWN":
        hard.append("PROJECT_COMPATIBILITY_NOT_EVALUATED")

    token_map = artifact.metadata.get("token_mapping_report")
    token_mapping_report = dict(token_map) if isinstance(token_map, dict) else {}
    design_system_state = (
        "PASS" if token_mapping_report.get("complete") is True else "PARTIAL"
    )
    if code_kind and design_system_state != "PASS":
        hard.append("DESIGN_SYSTEM_ADAPTATION_REQUIRED")
        obligations.append("DESIGN_SYSTEM_TOKEN_ADAPTATION_REQUIRED")

    reject_prefixes = (
        "LICENSE_REJECTED",
        "LICENSE_UNKNOWN",
        "FRAMEWORK_INCOMPATIBLE",
        "HIDDEN_REMOTE_RUNTIME",
        "SECURITY_FAILED",
        "ACCESSIBILITY_FAILED",
        "PROJECT_COMPATIBILITY_FAILED",
    )
    rejected = any(item.startswith(reject_prefixes) for item in hard)
    state = "REJECTED" if rejected else ("BLOCKED" if hard else "ADMITTED")
    return AdmissionDecision(
        framework_state=framework_state,
        license_state=license_state,
        dependency_state=dependency_state,
        security_state=security_state,
        accessibility_state=accessibility_state,
        design_system_state=design_system_state,
        token_mapping_report=token_mapping_report,
        unsupported_behaviors=unsupported,
        hard_failures=tuple(dict.fromkeys(hard)),
        validation_obligations=tuple(dict.fromkeys(obligations)),
        state=state,
    )
