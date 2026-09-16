"""Domain-neutral Source Intelligence automation-corpus primitives.

Archive validation, parsing, scanning and descriptor derivation are pure: this
module performs no network I/O and never evaluates workflow expressions.
"""

from __future__ import annotations

import io
import json
import posixpath
import re
import stat
import zipfile
from collections import Counter, defaultdict, deque
from hashlib import sha256
from pathlib import PurePosixPath
from typing import Any

from engine.core.errors import DdeError

SOURCE_REPOSITORY = "Zie619/n8n-workflows"
SOURCE_HOST = "codeload.github.com"
SOURCE_PATH_PREFIX = "/Zie619/n8n-workflows/zip/"
ACQUISITION_POLICY_VERSION = "dde-automation-corpus-acquisition-v2"
PARSER_VERSION = "dde-n8n-parser-v2"
SANITIZER_VERSION = "dde-automation-sanitizer-v2"
SCANNER_VERSION = "dde-automation-scanner-v2"
TOPOLOGY_COMPILER_VERSION = "dde-automation-topology-v2"

MAX_COMPRESSED_BYTES = 96 * 1024 * 1024
MAX_EXPANDED_BYTES = 512 * 1024 * 1024
MAX_WORKFLOW_COUNT = 10_000
MAX_WORKFLOW_BYTES = 2 * 1024 * 1024
MAX_LICENSE_BYTES = 256 * 1024

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SECRET_VALUE_RE = re.compile(
    r"(?i)(?:api[_-]?key|token|secret|password|client[_-]?secret|bearer)"
    r"\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{8,}"
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")
_PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d .()/-]{7,}\d)(?!\d)")
_PROMPT_RE = re.compile(
    r"(?i)(ignore (?:all |the )?(?:previous|prior) instructions|"
    r"act as (?:the )?system|system prompt|jailbreak|developer message|"
    r"tool call|override (?:the )?(?:system|policy)|do not follow)"
)
_EXPRESSION_RE = re.compile(r"(?:=\{\{|\{\{|\$json\b|\$env\b|\$node\b|\$credentials\b)")
_UNSAFE_SQL_RE = re.compile(
    r"(?is)(?:;\s*(?:drop|truncate|alter)\s+|\bexec(?:ute)?\s*\()"
)
_SECRET_KEYS = frozenset(
    {
        "apikey",
        "accesstoken",
        "authtoken",
        "bearertoken",
        "clientsecret",
        "password",
        "privatekey",
        "secret",
        "token",
        "webhooksecret",
    }
)
_PII_NAME_KEYS = frozenset(
    {"firstname", "lastname", "fullname", "customername", "contactname", "personname"}
)
_PII_ADDRESS_KEYS = frozenset(
    {"address", "streetaddress", "postaladdress", "shippingaddress", "billingaddress"}
)
_PII_IDENTIFIER_KEYS = frozenset(
    {"accountid", "customerid", "nationalid", "paymentid", "personid", "userid"}
)
_FINANCIAL_KEYS = frozenset(
    {"iban", "cardnumber", "creditcard", "bankaccount", "paymenttoken"}
)
_NESTED_ARCHIVE_SUFFIXES = (
    ".zip",
    ".tar",
    ".tgz",
    ".tar.gz",
    ".tar.bz2",
    ".tar.xz",
    ".7z",
    ".rar",
)
_NODE_CLASSES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("webhook",), "WEBHOOK_TRIGGER"),
    (("schedule", "cron"), "SCHEDULE_TRIGGER"),
    (("httprequest", "http_request"), "HTTP_REQUEST"),
    (("postgres", "mysql", "mssql", "sqlite", "database"), "DATABASE"),
    (("if", "switch", "filter"), "BRANCH"),
    (("splitinbatches", "loop", "itemlists"), "LOOP"),
    (("wait", "delay"), "DELAY"),
    (("rabbitmq", "kafka", "queue"), "QUEUE"),
    (("s3", "googledrive", "dropbox", "file"), "FILE_STORAGE"),
    (("slack", "email", "telegram", "discord", "notification"), "NOTIFICATION"),
    (("openai", "anthropic", "gemini", "llm", "agent", "chatmodel"), "AI_MODEL_CALL"),
    (("oauth", "auth"), "AUTH_EXCHANGE"),
    (("form", "approval"), "HUMAN_APPROVAL"),
    (("metrics", "logging", "sentry", "observability"), "OBSERVABILITY"),
    (("code", "function", "executecommand", "shell"), "CODE_EXECUTION"),
    (("set", "merge", "aggregate", "transform"), "TRANSFORM"),
)


def _hash(value: bytes | str | object) -> str:
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, str):
        raw = value.encode()
    else:
        raw = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    return sha256(raw).hexdigest()


def exact_snapshot_url(commit_sha: str) -> str:
    """Return the sole EDR-0018 acquisition URL for an immutable revision."""
    if not _SHA_RE.fullmatch(commit_sha):
        raise DdeError(
            "POLICY_DENIED",
            "automation corpus revision must be a lowercase 40-character Git SHA",
        )
    return f"https://{SOURCE_HOST}{SOURCE_PATH_PREFIX}{commit_sha}"


def validate_snapshot_url(uri: str, commit_sha: str) -> None:
    expected = exact_snapshot_url(commit_sha)
    if uri != expected:
        raise DdeError(
            "POLICY_DENIED",
            "automation corpus URI is outside the exact EDR-0018 host/path authority",
            details={"expected": expected},
        )


def validate_http_response(*, status_code: int, location: str | None) -> None:
    """Reject redirects and non-success before any body becomes evidence."""
    if 300 <= status_code < 400 or location:
        raise DdeError("POLICY_DENIED", "automation corpus redirects are forbidden")
    if not 200 <= status_code < 300:
        raise DdeError(
            "EXTERNAL_DEPENDENCY_FAILURE",
            "automation corpus acquisition returned a non-success status",
            details={"status_code": status_code},
        )


def _normalize_member(name: str) -> str:
    value = name.replace("\\", "/")
    if "\x00" in value or not value:
        raise DdeError("POLICY_DENIED", "archive member path is malformed")
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise DdeError("POLICY_DENIED", "archive absolute paths are forbidden")
    normalized = posixpath.normpath(value)
    if normalized in {"", ".", ".."} or normalized.startswith("../"):
        raise DdeError("POLICY_DENIED", "archive traversal is forbidden")
    return normalized


def safe_zip_members(archive: bytes) -> tuple[list[zipfile.ZipInfo], int]:
    if len(archive) > MAX_COMPRESSED_BYTES:
        raise DdeError("BUDGET_EXCEEDED", "compressed automation corpus exceeds 96 MiB")
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            infos = zf.infolist()
    except zipfile.BadZipFile as exc:
        raise DdeError("POLICY_DENIED", "automation corpus is not a valid ZIP") from exc
    seen: set[str] = set()
    expanded = 0
    workflows = 0
    accepted: list[zipfile.ZipInfo] = []
    for info in infos:
        normalized = _normalize_member(info.filename)
        if normalized in seen:
            raise DdeError(
                "POLICY_DENIED", "archive contains duplicate normalized paths"
            )
        seen.add(normalized)
        mode = (info.external_attr >> 16) & 0xFFFF
        file_type = stat.S_IFMT(mode)
        if file_type and file_type not in {stat.S_IFREG, stat.S_IFDIR}:
            raise DdeError(
                "POLICY_DENIED", "archive links and special files are forbidden"
            )
        lower = normalized.lower()
        if any(lower.endswith(suffix) for suffix in _NESTED_ARCHIVE_SUFFIXES):
            raise DdeError("POLICY_DENIED", "nested archives are forbidden")
        expanded += info.file_size
        if expanded > MAX_EXPANDED_BYTES:
            raise DdeError(
                "BUDGET_EXCEEDED", "expanded automation corpus exceeds 512 MiB"
            )
        if info.is_dir():
            accepted.append(info)
            continue
        if lower.endswith(".json"):
            workflows += 1
            if workflows > MAX_WORKFLOW_COUNT:
                raise DdeError(
                    "BUDGET_EXCEEDED",
                    "automation corpus exceeds 10,000 workflows",
                )
            if info.file_size > MAX_WORKFLOW_BYTES:
                raise DdeError("BUDGET_EXCEEDED", "workflow JSON exceeds 2 MiB")
        accepted.append(info)
    return accepted, expanded


def license_evidence(
    archive: bytes, infos: list[zipfile.ZipInfo]
) -> tuple[str, str | None]:
    candidates = {"license", "license.md", "license.txt", "copying"}
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        for info in sorted(infos, key=lambda item: item.filename.lower()):
            if info.is_dir() or info.file_size > MAX_LICENSE_BYTES:
                continue
            basename = PurePosixPath(info.filename).name.lower()
            if basename not in candidates:
                continue
            text = zf.read(info).decode("utf-8", errors="replace").lower()
            if "mit license" in text and "permission is hereby granted" in text:
                return "VERIFIED", _normalize_member(info.filename)
    return "REJECTED", None


def _walk(value: object, *, parent_key: str = "") -> list[tuple[str, object]]:
    output: list[tuple[str, object]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            output.append((normalized, child))
            output.extend(_walk(child, parent_key=normalized))
    elif isinstance(value, list):
        for child in value:
            output.extend(_walk(child, parent_key=parent_key))
    return output


def _string_values(value: object) -> list[str]:
    output: list[str] = []
    if isinstance(value, str):
        output.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            output.extend(_string_values(child))
    elif isinstance(value, list):
        for child in value:
            output.extend(_string_values(child))
    return output


def _node_class(node: dict[str, Any]) -> str:
    raw_type = str(node.get("type") or "").lower().replace("-", "").replace("_", "")
    parameters = node.get("parameters")
    for needles, result in _NODE_CLASSES:
        if any(needle.replace("_", "") in raw_type for needle in needles):
            if result == "DATABASE" and isinstance(parameters, dict):
                operation = str(parameters.get("operation") or "").lower()
                if any(
                    word in operation
                    for word in ("insert", "update", "delete", "write")
                ):
                    return "DATABASE_WRITE"
                return "DATABASE_READ"
            return result
    return "OTHER"


def scan_workflow(payload: dict[str, Any]) -> tuple[str, ...]:
    """Static scan only. Expressions, commands, SQL and URLs are never evaluated."""
    findings: set[str] = set()
    rendered = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    if _SECRET_VALUE_RE.search(rendered) or _BEARER_RE.search(rendered):
        findings.add("SECRET_LITERAL")
    if _PRIVATE_KEY_RE.search(rendered):
        findings.add("PRIVATE_KEY_MATERIAL")
    if _EMAIL_RE.search(rendered):
        findings.add("PII_EMAIL")
    if _PHONE_RE.search(rendered):
        findings.add("PII_PHONE")
    if _PROMPT_RE.search(rendered):
        findings.add("PROMPT_INJECTION_TEXT")
    if _EXPRESSION_RE.search(rendered):
        findings.add("DYNAMIC_EXPRESSION_PRESENT")
    for key, value in _walk(payload):
        if key in _SECRET_KEYS and value not in (None, "", {}, []):
            findings.add("SECRET_LITERAL")
        if key in _PII_NAME_KEYS and isinstance(value, str) and value.strip():
            findings.add("PII_NAME")
        if key in _PII_ADDRESS_KEYS and value not in (None, "", {}, []):
            findings.add("PII_ADDRESS")
        if key in _PII_IDENTIFIER_KEYS and value not in (None, "", {}, []):
            findings.add("PII_IDENTIFIER")
        if key in _FINANCIAL_KEYS and value not in (None, "", {}, []):
            findings.add("PII_FINANCIAL")
    nodes = payload.get("nodes")
    if not isinstance(nodes, list):
        return tuple(sorted(findings))
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_class = _node_class(node)
        parameters = node.get("parameters")
        if node.get("credentials"):
            findings.add("CREDENTIAL_REFERENCE")
        if node_class == "CODE_EXECUTION":
            findings.add("CODE_OR_COMMAND_EXECUTION")
        if node_class == "HTTP_REQUEST":
            findings.add("NETWORK_EFFECT")
            if any(_EXPRESSION_RE.search(text) for text in _string_values(parameters)):
                findings.add("DYNAMIC_NETWORK_TARGET")
        if node_class in {"DATABASE_READ", "DATABASE_WRITE"}:
            if any(_UNSAFE_SQL_RE.search(text) for text in _string_values(parameters)):
                findings.add("UNSAFE_SQL_TEXT")
    return tuple(sorted(findings))


def _connections(
    payload: dict[str, Any], names: dict[str, int]
) -> list[tuple[int, int]]:
    raw = payload.get("connections")
    edges: set[tuple[int, int]] = set()
    if not isinstance(raw, dict):
        return []
    for source_name, groups in raw.items():
        source = names.get(str(source_name))
        if source is None or not isinstance(groups, dict):
            continue
        for outputs in groups.values():
            if not isinstance(outputs, list):
                continue
            for channel in outputs:
                if not isinstance(channel, list):
                    continue
                for target in channel:
                    if not isinstance(target, dict):
                        continue
                    target_index = names.get(str(target.get("node") or ""))
                    if target_index is not None:
                        edges.add((source, target_index))
    return sorted(edges)


def _strongly_connected(
    node_count: int, edges: list[tuple[int, int]]
) -> list[list[int]]:
    adjacency: dict[int, list[int]] = defaultdict(list)
    reverse: dict[int, list[int]] = defaultdict(list)
    for left, right in edges:
        adjacency[left].append(right)
        reverse[right].append(left)
    visited: set[int] = set()
    order: list[int] = []
    for root in range(node_count):
        if root in visited:
            continue
        stack: list[tuple[int, bool]] = [(root, False)]
        while stack:
            node, expanded = stack.pop()
            if expanded:
                order.append(node)
                continue
            if node in visited:
                continue
            visited.add(node)
            stack.append((node, True))
            for nxt in sorted(adjacency[node], reverse=True):
                if nxt not in visited:
                    stack.append((nxt, False))
    visited.clear()
    components: list[list[int]] = []
    for root in reversed(order):
        if root in visited:
            continue
        component: list[int] = []
        queue = [root]
        visited.add(root)
        while queue:
            node = queue.pop()
            component.append(node)
            for nxt in sorted(reverse[node], reverse=True):
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
        components.append(sorted(component))
    return sorted(components, key=lambda item: (item[0] if item else -1, len(item)))


def topology(payload: dict[str, Any]) -> dict[str, object]:
    raw_nodes = payload.get("nodes")
    nodes = (
        [item for item in raw_nodes if isinstance(item, dict)]
        if isinstance(raw_nodes, list)
        else []
    )
    ordered = sorted(
        nodes,
        key=lambda item: (
            str(item.get("name") or ""),
            str(item.get("type") or ""),
            _hash(item.get("parameters") or {}),
        ),
    )
    names = {str(node.get("name") or ""): index for index, node in enumerate(ordered)}
    edges = _connections(payload, names)
    classes = [_node_class(node) for node in ordered]
    class_counts = dict(sorted(Counter(classes).items()))
    incoming = Counter(right for _, right in edges)
    outgoing = Counter(left for left, _ in edges)
    branches = sum(1 for index in range(len(ordered)) if outgoing[index] > 1)
    merges = sum(1 for index in range(len(ordered)) if incoming[index] > 1)
    self_loops = sum(1 for left, right in edges if left == right)
    components = _strongly_connected(len(ordered), edges)
    cyclic = [
        component
        for component in components
        if len(component) > 1 or any((node, node) in edges for node in component)
    ]
    weak: dict[int, set[int]] = defaultdict(set)
    for left, right in edges:
        weak[left].add(right)
        weak[right].add(left)
    unseen = set(range(len(ordered)))
    weak_sizes: list[int] = []
    while unseen:
        root = min(unseen)
        queue = deque([root])
        unseen.remove(root)
        size = 0
        while queue:
            node = queue.popleft()
            size += 1
            for nxt in sorted(weak[node]):
                if nxt in unseen:
                    unseen.remove(nxt)
                    queue.append(nxt)
        weak_sizes.append(size)
    semantic = {
        "node_count": len(ordered),
        "edge_count": len(edges),
        "class_counts": class_counts,
        "edges": [(classes[left], classes[right]) for left, right in edges],
        "branch_count": branches,
        "merge_count": merges,
        "self_loop_count": self_loops,
        "scc_sizes": sorted(len(item) for item in components),
        "cyclic_scc_sizes": sorted(len(item) for item in cyclic),
        "weak_component_sizes": sorted(weak_sizes),
        "disconnected": len(weak_sizes) > 1,
    }
    return {**semantic, "topology_hash": _hash(semantic)}


def _safe_text(value: object, *, maximum: int = 160) -> str:
    text = str(value or "").strip()
    text = _EMAIL_RE.sub("[redacted-email]", text)
    text = _PHONE_RE.sub("[redacted-phone]", text)
    text = _SECRET_VALUE_RE.sub("[redacted-secret]", text)
    text = _BEARER_RE.sub("[redacted-secret]", text)
    return text[:maximum]


def describe_workflow(path: str, raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_WORKFLOW_BYTES:
        raise DdeError("BUDGET_EXCEEDED", "workflow JSON exceeds 2 MiB")
    raw_hash = _hash(raw)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DdeError("POLICY_DENIED", "workflow JSON is malformed") from exc
    if not isinstance(payload, dict):
        raise DdeError("POLICY_DENIED", "workflow JSON root must be an object")
    findings = scan_workflow(payload)
    top = topology(payload)
    raw_nodes = payload.get("nodes")
    nodes = (
        [item for item in raw_nodes if isinstance(item, dict)]
        if isinstance(raw_nodes, list)
        else []
    )
    classes = sorted({_node_class(item) for item in nodes})
    triggers = [item for item in classes if item.endswith("_TRIGGER")]
    actions = [item for item in classes if not item.endswith("_TRIGGER")]
    unsafe = {
        "SECRET_LITERAL",
        "PRIVATE_KEY_MATERIAL",
        "PII_EMAIL",
        "PII_PHONE",
        "PII_NAME",
        "PII_ADDRESS",
        "PII_IDENTIFIER",
        "PII_FINANCIAL",
        "PROMPT_INJECTION_TEXT",
        "CODE_OR_COMMAND_EXECUTION",
        "UNSAFE_SQL_TEXT",
    }
    polarity = "ANTI_PATTERN" if unsafe.intersection(findings) else "POSITIVE"
    archetype = " -> ".join(triggers[:2] + actions[:4]) or "EMPTY_WORKFLOW"
    lineage_payload = {
        "archetype": archetype,
        "classes": classes,
        "topology": {
            key: value for key, value in top.items() if key != "topology_hash"
        },
    }
    lineage = _hash(lineage_payload)
    revision = _hash(
        {
            "lineage": lineage,
            "raw_hash": raw_hash,
            "parser": PARSER_VERSION,
            "sanitizer": SANITIZER_VERSION,
            "scanner": SCANNER_VERSION,
            "topology_compiler": TOPOLOGY_COMPILER_VERSION,
        }
    )
    security_findings = [
        item
        for item in findings
        if not item.startswith("PII_")
        and item not in {"SECRET_LITERAL", "PRIVATE_KEY_MATERIAL"}
    ]
    pii_findings = [item for item in findings if item.startswith("PII_")]
    secret_findings = [
        item
        for item in findings
        if item in {"SECRET_LITERAL", "PRIVATE_KEY_MATERIAL", "CREDENTIAL_REFERENCE"}
    ]
    prompt_findings = [item for item in findings if item == "PROMPT_INJECTION_TEXT"]
    implementation_guidance = (
        ["Use the sanitized control-flow and resilience shape as reference only."]
        if polarity == "POSITIVE"
        else []
    )
    anti_notes = (
        [
            "Unsafe or sensitive characteristics make this descriptor negative "
            "guidance only."
        ]
        if polarity == "ANTI_PATTERN"
        else []
    )
    capsule = {
        "pattern_lineage_id": lineage,
        "pattern_revision_hash": revision,
        "archetype": archetype,
        "guidance_polarity": polarity,
        "trigger_classes": triggers,
        "action_classes": actions,
        "control_flow": {
            "branch_count": top["branch_count"],
            "merge_count": top["merge_count"],
            "cyclic_scc_sizes": top["cyclic_scc_sizes"],
            "disconnected": top["disconnected"],
        },
        "resilience_controls": [
            item
            for item in classes
            if item in {"RETRY", "ERROR_HANDLER", "QUEUE", "DELAY"}
        ],
        "security_findings": sorted(security_findings),
        "implementation_guidance": implementation_guidance,
        "anti_pattern_notes": anti_notes,
    }
    descriptor_payload = {
        "pattern_lineage_id": lineage,
        "pattern_revision_hash": revision,
        "archetype": archetype,
        "guidance_polarity": polarity,
        "title": _safe_text(payload.get("name") or PurePosixPath(path).stem),
        "summary": f"Sanitized automation pattern: {archetype}.",
        "trigger_classes": triggers,
        "action_classes": actions,
        "integration_classes": classes,
        "control_flow": {
            key: value for key, value in top.items() if key != "topology_hash"
        },
        "resilience_controls": capsule["resilience_controls"],
        "security_controls": [],
        "observability_controls": [item for item in classes if item == "OBSERVABILITY"],
        "failure_modes": sorted(findings),
        "required_capabilities": [],
        "stack_constraints": {},
        "topology_hash": top["topology_hash"],
        "topology_compiler_version": TOPOLOGY_COMPILER_VERSION,
        "security_findings": sorted(security_findings),
        "pii_findings": sorted(pii_findings),
        "secret_findings": sorted(secret_findings),
        "prompt_findings": sorted(prompt_findings),
        "implementation_guidance": implementation_guidance,
        "anti_pattern_notes": anti_notes,
        "auth_pattern": {"credential_resolution": "FORBIDDEN"},
        "retry_error_pattern": {
            "has_retry_or_delay": any(item in classes for item in {"RETRY", "DELAY"}),
            "has_error_handler": "ERROR_HANDLER" in classes,
        },
        "idempotency_pattern": {"inferred": False},
        "persistence_pattern": {
            "classes": [
                item
                for item in classes
                if item in {"DATABASE_WRITE", "FILE_STORAGE", "QUEUE"}
            ]
        },
        "worker_safe_capsule": capsule,
        "parser_version": PARSER_VERSION,
        "sanitizer_version": SANITIZER_VERSION,
        "scanner_version": SCANNER_VERSION,
    }
    return {
        **descriptor_payload,
        "descriptor_hash": _hash(descriptor_payload),
        "raw_hash": raw_hash,
        "raw_size_bytes": len(raw),
        "findings": list(findings),
        "path": _normalize_member(path),
    }


def analyze_archive(
    archive: bytes, *, workflow_limit: int | None = None
) -> tuple[list[dict[str, Any]], int]:
    infos, expanded = safe_zip_members(archive)
    limit = workflow_limit if workflow_limit is not None else MAX_WORKFLOW_COUNT
    if limit < 0:
        raise DdeError("POLICY_DENIED", "workflow_limit must be non-negative")
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        workflows = [
            info
            for info in infos
            if not info.is_dir() and info.filename.lower().endswith(".json")
        ]
        ordered_workflows = sorted(
            workflows, key=lambda item: _normalize_member(item.filename)
        )
        for info in ordered_workflows[:limit]:
            raw = zf.read(info)
            try:
                row = describe_workflow(_normalize_member(info.filename), raw)
            except DdeError as exc:
                rows.append(
                    {
                        "path": _normalize_member(info.filename),
                        "raw": raw,
                        "raw_hash": _hash(raw),
                        "raw_size_bytes": len(raw),
                        "state": "REJECTED",
                        "parser_state": "REJECTED",
                        "findings": [exc.error_code],
                    }
                )
                continue
            unsafe = {
                "SECRET_LITERAL",
                "PRIVATE_KEY_MATERIAL",
                "PII_EMAIL",
                "PII_PHONE",
                "PII_NAME",
                "PII_ADDRESS",
                "PII_IDENTIFIER",
                "PII_FINANCIAL",
            }
            state = "BLOCKED" if unsafe.intersection(row["findings"]) else "SANITIZED"
            rows.append(
                {
                    **row,
                    "raw": raw,
                    "state": state,
                    "parser_state": "PARSED",
                    "source_metadata": {
                        "member_path": _normalize_member(info.filename)
                    },
                }
            )
    return rows, expanded
