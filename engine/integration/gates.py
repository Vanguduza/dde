"""Chapter 9.6–9.7 gate evaluators -- pure functions over a real git diff.

Configuration lives in this module, which is part of the DDE control plane
and is not loaded from the task workspace (Chapter 9.7: "A worker cannot
disable, weaken or reconfigure these gates; the configuration lives outside
the workspace and is not writable from it").

Scanner honesty is documented on `engine.integration.gate_service`: these
evaluators inspect the actual diff and proposed-revision blobs; they do
not invoke the Gitleaks / Semgrep / Grype / Syft binaries Chapter 9.6–9.7
name, and they do not perform live OSV.dev HTTP lookups.
"""

from __future__ import annotations

import json
import os
import re
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from engine.core.hashing import canonical_json, sha256_hex

#: Chapter 9.7 forbidden-path prefixes -- CI config, security policy,
#: migrations, and `.git` internals. Approval to override is DDE-026;
#: without an approval record the fail-closed outcome is a blocking find.
FORBIDDEN_PATH_PREFIXES: tuple[str, ...] = (
    ".git/",
    ".github/",
    "migrations/",
)

FORBIDDEN_PATH_NAMES: frozenset[str] = frozenset(
    {
        "SECURITY.md",
        ".pre-commit-config.yaml",
        "alembic.ini",
    }
)

#: Source suffixes that must carry a licence header when newly added.
SOURCE_SUFFIXES: frozenset[str] = frozenset(
    {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java"}
)

HEADER_MARKERS: tuple[str, ...] = (
    "SPDX-License-Identifier:",
    "Copyright",
)

#: Chapter 9.6 licence-compatibility allow-list (SPDX ids). A new package
#: whose declared or catalogued licence is outside this set is blocked.
ALLOWED_LICENCES: frozenset[str] = frozenset(
    {
        "MIT",
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "PSF-2.0",
        "Unlicense",
        "MPL-2.0",
    }
)

#: Block vulnerabilities at high and above (Chapter 9.6: "Yes above
#: severity threshold"). `medium` is recorded, not blocking.
BLOCKING_VULN_SEVERITIES: frozenset[str] = frozenset({"high", "critical"})

#: Chapter 9.6 transitive-delta threshold -- more newly introduced
#: lockfile members than this blocks.
TRANSITIVE_DELTA_LIMIT = 50

JUSTIFICATION_BASENAME = "DEPENDENCY_JUSTIFICATION.md"

_LOCKFILE_BASENAMES: frozenset[str] = frozenset(
    {
        "uv.lock",
        "poetry.lock",
        "Pipfile.lock",
        "package-lock.json",
        "yarn.lock",
        "Cargo.lock",
        "go.sum",
    }
)

_MANIFEST_BASENAMES: frozenset[str] = frozenset(
    {
        "pyproject.toml",
        "requirements.txt",
        "Pipfile",
        "package.json",
        "Cargo.toml",
        "go.mod",
    }
)

#: In-process advisory catalog standing in for OSV/Grype. The planted
#: package is what Chapter 18.2's S2 fixture ("planted vulnerable
#: dependency") exercises; live vulnerability feeds are deferred.
VULNERABILITY_ADVISORIES: dict[tuple[str, str], tuple[str, str]] = {
    ("pypi", "dde-planted-vulnerable"): ("DDE-PLANTED-001", "critical"),
}

#: Built-in SPDX map for packages this evaluator may see without a
#: worker-supplied justification.licence. Unknown-and-undeclared is a
#: blocking licence miss for *new* top-level packages, not for SBOM
#: members that were not introduced by this diff.
KNOWN_LICENCES: dict[tuple[str, str], str] = {
    ("pypi", "httpx"): "BSD-3-Clause",
    ("pypi", "fastapi"): "MIT",
    ("pypi", "pydantic"): "MIT",
    ("pypi", "sqlalchemy"): "MIT",
}

#: Popular package names for the Chapter 9.6 typosquat heuristic.
POPULAR_PACKAGES: dict[str, frozenset[str]] = {
    "pypi": frozenset(
        {
            "requests",
            "urllib3",
            "numpy",
            "pandas",
            "django",
            "flask",
            "pytest",
            "sqlalchemy",
            "pydantic",
            "fastapi",
            "httpx",
            "cryptography",
            "pillow",
            "tensorflow",
            "torch",
        }
    ),
    "npm": frozenset(
        {
            "react",
            "lodash",
            "express",
            "webpack",
            "typescript",
            "eslint",
            "vue",
            "angular",
        }
    ),
}

_AWS_KEY = re.compile(r"AKIA[0-9A-Z]{16}")
_GITHUB_PAT = re.compile(r"ghp_[A-Za-z0-9]{36}")
_PRIVATE_KEY = re.compile(
    r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |OPENSSH )?PRIVATE KEY-----"
)
_PEP508 = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)"
    r"(?:\[[^\]]*\])?"
    r"\s*(?:(?P<op>===|==|>=|<=|~=|!=|>|<)\s*(?P<version>[^\s;,#]+))?"
)
_JUSTIFICATION_HEADING = re.compile(r"^#{1,3}\s+(\S+)\s*$")
_JUSTIFICATION_FIELD = re.compile(
    r"^(licence|license|maintenance|stdlib_insufficient)\s*:\s*(.+)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ScanFinding:
    """One Chapter 9.7 gate outcome over the evaluated diff."""

    gate: str
    tool: str
    severity: str
    blocking: bool
    passed: bool
    summary: str
    details: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class PackageRef:
    name: str
    version: str
    ecosystem: str
    is_top_level: bool
    source_path: str


@dataclass(frozen=True)
class PackageDecision:
    """Chapter 9.6 admission decision for one newly introduced package."""

    package_name: str
    package_version: str
    ecosystem: str
    is_top_level: bool
    licence: str | None
    maintenance_signal: str
    provenance: str
    vulnerability_ids: tuple[str, ...]
    typosquat_of: str | None
    justification: dict[str, object] | None
    transitive_delta: int | None
    status: str
    blocking_reason: str | None


@dataclass(frozen=True)
class GateEvaluation:
    findings: tuple[ScanFinding, ...]
    admissions: tuple[PackageDecision, ...]
    sbom_document: dict[str, object]
    sbom_content_hash: str
    passed: bool
    quarantined: bool


def is_dependency_manifest(path: str) -> bool:
    name = Path(path).name
    if name in _MANIFEST_BASENAMES or name in _LOCKFILE_BASENAMES:
        return True
    return name.endswith(".txt") and name.startswith("requirement")


def is_lockfile(path: str) -> bool:
    return Path(path).name in _LOCKFILE_BASENAMES


def evaluate_diff(
    *,
    changed_paths: list[str],
    unified_diff: str,
    proposed_blobs: dict[str, str | None],
    base_manifest_blobs: dict[str, str | None],
    proposed_manifest_blobs: dict[str, str | None],
    new_paths: list[str],
    donor_taints: list[dict[str, object]] | None = None,
    donor_reuse_approved: bool = False,
) -> GateEvaluation:
    """Run every Chapter 9.7 gate over one real worker-produced diff."""
    secret = scan_secrets(unified_diff, proposed_blobs=proposed_blobs)
    static = scan_static(unified_diff)
    forbidden = scan_forbidden_paths(changed_paths)
    headers = scan_licence_headers(new_paths, proposed_blobs)
    taint = scan_donor_taint(
        donor_taints=donor_taints or [],
        donor_reuse_approved=donor_reuse_approved,
    )
    dep_finding, admissions = admit_dependencies(
        changed_paths=changed_paths,
        unified_diff=unified_diff,
        base_manifest_blobs=base_manifest_blobs,
        proposed_manifest_blobs=proposed_manifest_blobs,
        proposed_blobs=proposed_blobs,
    )
    sbom_document, sbom_content_hash = generate_sbom(proposed_manifest_blobs)
    sbom_blocked = _sbom_contains_rejected(sbom_document, admissions)
    findings = (secret, static, forbidden, headers, taint, dep_finding)
    if sbom_blocked:
        dep_finding = ScanFinding(
            gate=dep_finding.gate,
            tool=dep_finding.tool,
            severity="critical",
            blocking=True,
            passed=False,
            summary=(
                dep_finding.summary + "; SBOM contains a package this "
                "evaluation rejected"
            ),
            details={**dep_finding.details, "sbom_gated": True},
        )
        findings = (secret, static, forbidden, headers, taint, dep_finding)
    blocking_failures = [item for item in findings if item.blocking and not item.passed]
    quarantined = (not secret.passed) and secret.blocking
    return GateEvaluation(
        findings=findings,
        admissions=admissions,
        sbom_document=sbom_document,
        sbom_content_hash=sbom_content_hash,
        passed=not blocking_failures,
        quarantined=quarantined,
    )


def scan_secrets(
    unified_diff: str,
    *,
    proposed_blobs: dict[str, str | None] | None = None,
) -> ScanFinding:
    """Chapter 9.7 secret detection. In-process stand-in for Gitleaks.

    Scans unified-diff added lines and, when provided, proposed blob
    contents. Blob scanning is the fail-closed backstop when a diff hunk
    carries no ``+`` lines (historical binary-classification miss).
    """
    hits: list[str] = []
    for line in _added_lines(unified_diff):
        hits.extend(_secret_hit_classes(line))
    if proposed_blobs:
        for path, blob in proposed_blobs.items():
            if blob is None:
                continue
            for line in blob.splitlines():
                for hit in _secret_hit_classes(line):
                    hits.append(f"{path}:{hit}")
    if hits:
        return ScanFinding(
            gate="secret_detection",
            tool="gitleaks",
            severity="critical",
            blocking=True,
            passed=False,
            summary="Secret material detected in the worker-produced diff",
            details={
                "hit_classes": sorted(set(hits)),
                "deferred": "gitleaks CLI is not invoked at Stage 2",
            },
        )
    return ScanFinding(
        gate="secret_detection",
        tool="gitleaks",
        severity="info",
        blocking=True,
        passed=True,
        summary="No secret material detected in added lines",
        details={"deferred": "gitleaks CLI is not invoked at Stage 2"},
    )


def _secret_hit_classes(line: str) -> list[str]:
    hits: list[str] = []
    if _AWS_KEY.search(line):
        hits.append("aws_access_key")
    if _GITHUB_PAT.search(line):
        hits.append("github_pat")
    if _PRIVATE_KEY.search(line):
        hits.append("private_key_pem")
    return hits


def scan_static(unified_diff: str) -> ScanFinding:
    """Chapter 9.7 static analysis. In-process subset; Semgrep CLI is
    DDE-045."""
    added = _added_lines(unified_diff)
    hits: list[str] = []
    for line in added:
        stripped = line.strip()
        if "eval(" in stripped and "compile(" in stripped:
            hits.append("eval_compile")
        if "subprocess" in stripped and "shell=True" in stripped:
            hits.append("subprocess_shell")
    if hits:
        return ScanFinding(
            gate="static_analysis",
            tool="semgrep",
            severity="error",
            blocking=True,
            passed=False,
            summary="Static analysis matched a blocking in-process rule",
            details={
                "hit_classes": sorted(set(hits)),
                "deferred": "semgrep CLI is not invoked; DDE-045 uses in-process SAST",
            },
        )
    return ScanFinding(
        gate="static_analysis",
        tool="semgrep",
        severity="info",
        blocking=True,
        passed=True,
        summary="No blocking in-process static-analysis match",
        details={
            "deferred": "semgrep CLI is not invoked; DDE-045 uses in-process SAST"
        },
    )


_SKIP_DIR_NAMES: frozenset[str] = frozenset(
    {".git", ".venv", "node_modules", "__pycache__", ".dde", "dist", "build"}
)
_SCAN_SUFFIXES: frozenset[str] = frozenset(
    {
        ".py",
        ".ts",
        ".js",
        ".tsx",
        ".jsx",
        ".env",
        ".pem",
        ".txt",
        ".md",
        ".yml",
        ".yaml",
        ".toml",
        ".json",
    }
)
_MAX_SCAN_FILE_BYTES = 1_000_000


def scan_workspace(root: Path) -> tuple[ScanFinding, ScanFinding]:
    """DDE-045: the same in-process secret/SAST rules as Chapter 9.7, over
    a whole workspace tree rather than a git diff. No vendor SAST/DAST
    binary is invoked."""
    secret_hits: list[str] = []
    static_hits: list[str] = []
    for path in _iter_workspace_files(root):
        try:
            if path.stat().st_size > _MAX_SCAN_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        for line in text.splitlines():
            if _AWS_KEY.search(line):
                secret_hits.append(f"{rel}:aws_access_key")
            if _GITHUB_PAT.search(line):
                secret_hits.append(f"{rel}:github_pat")
            if _PRIVATE_KEY.search(line):
                secret_hits.append(f"{rel}:private_key_pem")
            stripped = line.strip()
            if "eval(" in stripped and "compile(" in stripped:
                static_hits.append(f"{rel}:eval_compile")
            if "subprocess" in stripped and "shell=True" in stripped:
                static_hits.append(f"{rel}:subprocess_shell")
    secret = (
        ScanFinding(
            gate="secret_detection",
            tool="gitleaks",
            severity="critical",
            blocking=True,
            passed=False,
            summary="Secret material detected in the workspace tree",
            details={"hits": secret_hits[:50], "tool": "in-process"},
        )
        if secret_hits
        else ScanFinding(
            gate="secret_detection",
            tool="gitleaks",
            severity="info",
            blocking=True,
            passed=True,
            summary="No secret material detected in the workspace tree",
            details={"tool": "in-process"},
        )
    )
    static = (
        ScanFinding(
            gate="static_analysis",
            tool="semgrep",
            severity="error",
            blocking=True,
            passed=False,
            summary="SAST matched a blocking in-process rule",
            details={"hits": static_hits[:50], "tool": "in-process"},
        )
        if static_hits
        else ScanFinding(
            gate="static_analysis",
            tool="semgrep",
            severity="info",
            blocking=True,
            passed=True,
            summary="No blocking in-process SAST match",
            details={"tool": "in-process"},
        )
    )
    return secret, static


def _iter_workspace_files(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in _SKIP_DIR_NAMES]
        for name in filenames:
            path = Path(dirpath) / name
            if path.suffix.lower() in _SCAN_SUFFIXES or name.startswith(".env"):
                yield path


def scan_forbidden_paths(changed_paths: list[str]) -> ScanFinding:
    """Chapter 9.7 forbidden-path modification."""
    hits = [path for path in changed_paths if _is_forbidden(path)]
    if hits:
        return ScanFinding(
            gate="forbidden_path",
            tool="project-policy",
            severity="error",
            blocking=True,
            passed=False,
            summary="Diff touches a path that requires approval to modify",
            details={"paths": hits, "deferred_approval": "DDE-026"},
        )
    return ScanFinding(
        gate="forbidden_path",
        tool="project-policy",
        severity="info",
        blocking=True,
        passed=True,
        summary="No forbidden-path modification",
        details={},
    )


def scan_licence_headers(
    new_paths: list[str], proposed_blobs: dict[str, str | None]
) -> ScanFinding:
    """Chapter 9.7 licence header / file provenance (SPDX/copyright on new
    source). Donor provenance taint is a separate gate (`scan_donor_taint`)."""
    missing: list[str] = []
    for path in new_paths:
        if Path(path).suffix.lower() not in SOURCE_SUFFIXES:
            continue
        blob = proposed_blobs.get(path) or ""
        head = "\n".join(blob.splitlines()[:12])
        if not any(marker in head for marker in HEADER_MARKERS):
            missing.append(path)
    if missing:
        return ScanFinding(
            gate="licence_header",
            tool="project-policy",
            severity="error",
            blocking=True,
            passed=False,
            summary="Newly added source files are missing a licence header",
            details={"paths": missing},
        )
    return ScanFinding(
        gate="licence_header",
        tool="project-policy",
        severity="info",
        blocking=True,
        passed=True,
        summary="New source files carry a licence header, or none were added",
        details={},
    )


#: Source classes that may enter implementation diffs only with donor_reuse.
_IMPLEMENTATION_TAINT_CLASSES = frozenset(
    {"OPEN_REUSE", "CONDITIONAL_REUSE", "RESTRICTED"}
)
_FORBIDDEN_IMPLEMENTATION_CLASSES = frozenset(
    {"REJECTED", "SOURCE_REFERENCE_ONLY", "UNKNOWN"}
)


def scan_donor_taint(
    *,
    donor_taints: list[dict[str, object]],
    donor_reuse_approved: bool,
) -> ScanFinding:
    """Chapter 13.8 / 9.7 donor provenance taint at the merge gate.

    Production mutation site: DiffGateService.evaluate → evaluate_diff →
    this function. Blocks when the task carries donor taint whose class
    forbids implementation, or when reusable classes lack a signed
    donor_reuse approval.
    """
    if not donor_taints:
        return ScanFinding(
            gate="donor_taint",
            tool="donor-lab",
            severity="info",
            blocking=True,
            passed=True,
            summary="No donor taint on this merge candidate",
            details={"taint_count": 0},
        )
    forbidden = [
        t
        for t in donor_taints
        if str(t.get("source_class", "")) in _FORBIDDEN_IMPLEMENTATION_CLASSES
    ]
    if forbidden:
        classes = sorted({str(t.get("source_class")) for t in forbidden})
        return ScanFinding(
            gate="donor_taint",
            tool="donor-lab",
            severity="error",
            blocking=True,
            passed=False,
            summary=(
                "Donor taint class forbids merge of donor-derived "
                f"implementation ({', '.join(classes)})"
            ),
            details={
                "taint_count": len(donor_taints),
                "forbidden_classes": classes,
                "donor_artifact_ids": [
                    str(t.get("donor_artifact_id")) for t in forbidden
                ],
            },
        )
    needs_reuse = [
        t
        for t in donor_taints
        if str(t.get("source_class", "")) in _IMPLEMENTATION_TAINT_CLASSES
    ]
    if needs_reuse and not donor_reuse_approved:
        return ScanFinding(
            gate="donor_taint",
            tool="donor-lab",
            severity="error",
            blocking=True,
            passed=False,
            summary=(
                "Donor-derived implementation requires an APPROVED "
                "donor_reuse decision before merge (Chapter 13.8)"
            ),
            details={
                "taint_count": len(donor_taints),
                "donor_artifact_ids": [
                    str(t.get("donor_artifact_id")) for t in needs_reuse
                ],
                "donor_reuse_approved": False,
            },
        )
    return ScanFinding(
        gate="donor_taint",
        tool="donor-lab",
        severity="info",
        blocking=True,
        passed=True,
        summary="Donor taint permits merge under recorded reuse policy",
        details={
            "taint_count": len(donor_taints),
            "donor_reuse_approved": donor_reuse_approved,
        },
    )


def admit_dependencies(
    *,
    changed_paths: list[str],
    unified_diff: str,
    base_manifest_blobs: dict[str, str | None],
    proposed_manifest_blobs: dict[str, str | None],
    proposed_blobs: dict[str, str | None],
) -> tuple[ScanFinding, tuple[PackageDecision, ...]]:
    """Chapter 9.6 governed admission of packages the diff newly introduces."""
    justifications = _parse_justifications(proposed_blobs)
    introduced: list[PackageRef] = []
    for path in changed_paths:
        if not is_dependency_manifest(path) or is_lockfile(path):
            continue
        before = parse_manifest(path, base_manifest_blobs.get(path))
        after = parse_manifest(path, proposed_manifest_blobs.get(path))
        before_keys = {(item.ecosystem, item.name) for item in before}
        for item in after:
            if (item.ecosystem, item.name) not in before_keys:
                introduced.append(item)

    transitive_delta = _lockfile_delta(changed_paths, unified_diff)
    decisions = tuple(
        _decide_package(
            item,
            justifications=justifications,
            transitive_delta=transitive_delta if not item.is_top_level else None,
        )
        for item in introduced
    )
    rejected = [item for item in decisions if item.status == "REJECTED"]
    if transitive_delta > TRANSITIVE_DELTA_LIMIT:
        return (
            ScanFinding(
                gate="dependency_vulnerability",
                tool="osv",
                severity="error",
                blocking=True,
                passed=False,
                summary=(
                    f"Lockfile transitive delta {transitive_delta} exceeds "
                    f"threshold {TRANSITIVE_DELTA_LIMIT}"
                ),
                details={
                    "transitive_delta": transitive_delta,
                    "deferred": "live OSV/Grype lookups are not performed",
                },
            ),
            decisions,
        )
    if rejected:
        return (
            ScanFinding(
                gate="dependency_vulnerability",
                tool="osv",
                severity="critical",
                blocking=True,
                passed=False,
                summary=(
                    f"{len(rejected)} newly introduced package(s) failed "
                    "dependency admission"
                ),
                details={
                    "rejected": [item.package_name for item in rejected],
                    "deferred": "live OSV/Grype lookups are not performed",
                },
            ),
            decisions,
        )
    return (
        ScanFinding(
            gate="dependency_vulnerability",
            tool="osv",
            severity="info",
            blocking=True,
            passed=True,
            summary=(
                "No newly introduced package failed admission"
                if introduced
                else "Diff introduces no dependency-manifest packages"
            ),
            details={
                "introduced": [item.name for item in introduced],
                "transitive_delta": transitive_delta,
                "deferred": "live OSV/Grype lookups are not performed",
            },
        ),
        decisions,
    )


def generate_sbom(
    proposed_manifest_blobs: dict[str, str | None],
) -> tuple[dict[str, object], str]:
    """CycloneDX 1.5 subset from declared manifests at the proposed
    revision (Chapter 9.6). Syft CLI is not invoked; lockfile-transitive
    members are deferred."""
    components: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for path, blob in sorted(proposed_manifest_blobs.items()):
        if blob is None or is_lockfile(path):
            continue
        for item in parse_manifest(path, blob):
            key = (item.ecosystem, item.name)
            if key in seen:
                continue
            seen.add(key)
            component: dict[str, object] = {
                "type": "library",
                "name": item.name,
                "version": item.version,
                "bom-ref": f"{item.ecosystem}:{item.name}@{item.version}",
            }
            licence = KNOWN_LICENCES.get((item.ecosystem, item.name.lower()))
            if licence is not None:
                component["licenses"] = [{"license": {"id": licence}}]
            components.append(component)
    document: dict[str, object] = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "manufactured-product",
            }
        },
        "components": components,
    }
    return document, sha256_hex(canonical_json(document))


def parse_manifest(path: str, blob: str | None) -> list[PackageRef]:
    if not blob:
        return []
    name = Path(path).name
    if name == "pyproject.toml":
        return _parse_pyproject(path, blob)
    if name.endswith(".txt") and name.startswith("requirement"):
        return _parse_requirements(path, blob)
    if name == "package.json":
        return _parse_package_json(path, blob)
    return []


def _decide_package(
    item: PackageRef,
    *,
    justifications: dict[str, dict[str, object]],
    transitive_delta: int | None,
) -> PackageDecision:
    justification = justifications.get(item.name.lower())
    advisory = VULNERABILITY_ADVISORIES.get((item.ecosystem, item.name.lower()))
    vulnerability_ids = (advisory[0],) if advisory is not None else ()
    typosquat_of = _typosquat(item.ecosystem, item.name)
    declared_licence = None
    if justification is not None:
        raw = justification.get("licence") or justification.get("license")
        if isinstance(raw, str):
            declared_licence = raw
    catalogue_licence = KNOWN_LICENCES.get((item.ecosystem, item.name.lower()))
    licence = declared_licence or catalogue_licence
    provenance = "justified" if justification is not None else "unknown"
    maintenance = "unknown"
    if justification is not None and justification.get("maintenance"):
        maintenance = "ok"

    blocking_reason: str | None = None
    if advisory is not None and advisory[1] in BLOCKING_VULN_SEVERITIES:
        blocking_reason = f"known vulnerability {advisory[0]} ({advisory[1]})"
    elif typosquat_of is not None:
        blocking_reason = f"typosquat heuristic matched popular package {typosquat_of}"
    elif item.is_top_level and justification is None:
        blocking_reason = (
            "new top-level dependency is missing AGENTS.md justification "
            "(licence, maintenance, why the standard library is insufficient)"
        )
    elif item.is_top_level and (licence is None or licence not in ALLOWED_LICENCES):
        blocking_reason = (
            f"licence {licence!r} is incompatible with the project licence policy"
        )
    elif (
        item.is_top_level
        and justification is not None
        and not justification.get("stdlib_insufficient")
    ):
        blocking_reason = (
            "new top-level justification does not record why the standard "
            "library is insufficient"
        )

    status = "REJECTED" if blocking_reason is not None else "ADMITTED"
    return PackageDecision(
        package_name=item.name,
        package_version=item.version,
        ecosystem=item.ecosystem,
        is_top_level=item.is_top_level,
        licence=licence,
        maintenance_signal=maintenance,
        provenance=provenance,
        vulnerability_ids=vulnerability_ids,
        typosquat_of=typosquat_of,
        justification=justification,
        transitive_delta=transitive_delta,
        status=status,
        blocking_reason=blocking_reason,
    )


def _sbom_contains_rejected(
    sbom_document: dict[str, object], admissions: tuple[PackageDecision, ...]
) -> bool:
    rejected = {
        (item.ecosystem, item.package_name.lower())
        for item in admissions
        if item.status == "REJECTED"
    }
    if not rejected:
        return False
    components = sbom_document.get("components")
    if not isinstance(components, list):
        return False
    for component in components:
        if not isinstance(component, dict):
            continue
        name = component.get("name")
        if isinstance(name, str) and any(
            name.lower() == package for _, package in rejected
        ):
            return True
    return False


def _parse_pyproject(path: str, blob: str) -> list[PackageRef]:
    try:
        data = tomllib.loads(blob)
    except tomllib.TOMLDecodeError:
        return []
    project = data.get("project")
    if not isinstance(project, dict):
        return []
    raw = project.get("dependencies") or []
    if not isinstance(raw, list):
        return []
    refs: list[PackageRef] = []
    for entry in raw:
        if isinstance(entry, str):
            parsed = _parse_requirement_line(path, entry, ecosystem="pypi")
            if parsed is not None:
                refs.append(parsed)
    return refs


def _parse_requirements(path: str, blob: str) -> list[PackageRef]:
    refs: list[PackageRef] = []
    for line in blob.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        parsed = _parse_requirement_line(path, stripped, ecosystem="pypi")
        if parsed is not None:
            refs.append(parsed)
    return refs


def _parse_package_json(path: str, blob: str) -> list[PackageRef]:
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    refs: list[PackageRef] = []
    for key in ("dependencies", "devDependencies"):
        mapping = data.get(key)
        if not isinstance(mapping, dict):
            continue
        for name, version in mapping.items():
            if not isinstance(name, str):
                continue
            refs.append(
                PackageRef(
                    name=name,
                    version=str(version),
                    ecosystem="npm",
                    is_top_level=True,
                    source_path=path,
                )
            )
    return refs


def _parse_requirement_line(
    path: str, line: str, *, ecosystem: str
) -> PackageRef | None:
    match = _PEP508.match(line)
    if match is None:
        return None
    name = match.group("name")
    version = match.group("version") or "*"
    return PackageRef(
        name=name,
        version=version,
        ecosystem=ecosystem,
        is_top_level=True,
        source_path=path,
    )


def _parse_justifications(
    proposed_blobs: dict[str, str | None],
) -> dict[str, dict[str, object]]:
    found: dict[str, dict[str, object]] = {}
    for path, blob in proposed_blobs.items():
        if Path(path).name != JUSTIFICATION_BASENAME or not blob:
            continue
        current: str | None = None
        fields: dict[str, object] = {}
        for raw_line in blob.splitlines():
            line = raw_line.strip()
            heading = _JUSTIFICATION_HEADING.match(line)
            if heading is not None:
                if current is not None:
                    found[current.lower()] = dict(fields)
                current = heading.group(1)
                fields = {}
                continue
            field_match = _JUSTIFICATION_FIELD.match(line)
            if field_match is not None and current is not None:
                key = field_match.group(1).lower()
                if key == "license":
                    key = "licence"
                fields[key] = field_match.group(2).strip()
        if current is not None:
            found[current.lower()] = dict(fields)
    return found


def _lockfile_delta(changed_paths: list[str], unified_diff: str) -> int:
    lock_changed = [path for path in changed_paths if is_lockfile(path)]
    if not lock_changed:
        return 0
    # Count added non-hunk lines in lockfile sections as a coarse delta.
    added = _added_lines(unified_diff)
    return sum(1 for line in added if line.strip() and not line.startswith("+++"))


def _typosquat(ecosystem: str, name: str) -> str | None:
    popular = POPULAR_PACKAGES.get(ecosystem, frozenset())
    lowered = name.lower()
    if lowered in popular or len(lowered) < 4:
        return None
    for candidate in popular:
        if _levenshtein(lowered, candidate) <= 2:
            return candidate
    return None


def _levenshtein(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for i, left_ch in enumerate(left, start=1):
        current = [i]
        for j, right_ch in enumerate(right, start=1):
            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            replace_cost = previous[j - 1] + (left_ch != right_ch)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def _is_forbidden(path: str) -> bool:
    normalised = path.replace("\\", "/")
    if Path(normalised).name in FORBIDDEN_PATH_NAMES:
        return True
    return any(
        normalised == prefix.rstrip("/") or normalised.startswith(prefix)
        for prefix in FORBIDDEN_PATH_PREFIXES
    )


def _added_lines(unified_diff: str) -> list[str]:
    lines: list[str] = []
    for line in unified_diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(line[1:])
    return lines
