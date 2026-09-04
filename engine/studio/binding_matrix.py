"""DDE-069 golden-control binding ledger.

The canonical JSON records evidence independently for DOMAIN, READ, COMMAND,
STATE, UI, WIRED, E2E and VISUAL.  A visible control cannot become finally
VERIFIED merely because backend files and backend tests happen to exist.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from engine.core.errors import DdeError

MATRIX_RELATIVE: Final = "docs/truth/golden/frontend_binding_matrix.json"
RENDERED_RELATIVE: Final = "docs/truth/FRONTEND_STUDIO_BINDING_MATRIX.md"


class BindingStatus(StrEnum):
    UNBOUND = "UNBOUND"
    TYPED_UNAVAILABLE = "TYPED_UNAVAILABLE"
    BOUND = "BOUND"
    VERIFIED = "VERIFIED"


class EvidenceLayerName(StrEnum):
    DOMAIN = "DOMAIN"
    READ = "READ"
    COMMAND = "COMMAND"
    STATE = "STATE"
    UI = "UI"
    WIRED = "WIRED"
    E2E = "E2E"
    VISUAL = "VISUAL"


class EvidenceStatus(StrEnum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNBOUND = "UNBOUND"
    TYPED_UNAVAILABLE = "TYPED_UNAVAILABLE"
    BOUND = "BOUND"
    VERIFIED = "VERIFIED"
    BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"


@dataclass(frozen=True)
class BindingEvidence:
    layer: EvidenceLayerName
    applicable: bool
    status: EvidenceStatus
    implementation_refs: tuple[str, ...]
    test_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    note: str


@dataclass(frozen=True)
class BindingRow:
    id: str
    region: str
    feature: str
    visual_contract: str
    read_model: str | None
    command: str | None
    state_transition: str | None
    capability: str | None
    permission: str | None
    failure_states: tuple[str, ...]
    layers: Mapping[EvidenceLayerName, BindingEvidence]
    note: str

    @property
    def status(self) -> BindingStatus:
        required = [item for item in self.layers.values() if item.applicable]
        statuses = {item.status for item in required}
        if EvidenceStatus.UNBOUND in statuses:
            return BindingStatus.UNBOUND
        if statuses & {
            EvidenceStatus.TYPED_UNAVAILABLE,
            EvidenceStatus.BLOCKED_EXTERNAL,
        }:
            return BindingStatus.TYPED_UNAVAILABLE
        if required and all(
            item.status is EvidenceStatus.VERIFIED for item in required
        ):
            return BindingStatus.VERIFIED
        return BindingStatus.BOUND

    def layer(self, name: EvidenceLayerName) -> BindingEvidence:
        return self.layers[name]


@dataclass(frozen=True)
class BindingRegion:
    id: str
    title: str
    specification: str


@dataclass(frozen=True)
class BindingMatrix:
    version: int
    authority: str
    closure_rule: str
    regions: tuple[BindingRegion, ...]
    rows: tuple[BindingRow, ...]

    def by_status(self, status: BindingStatus) -> tuple[BindingRow, ...]:
        return tuple(row for row in self.rows if row.status is status)

    def rows_for(self, region_id: str) -> tuple[BindingRow, ...]:
        return tuple(row for row in self.rows if row.region == region_id)


def _seq(entry: Mapping[str, object], key: str, *, row_id: str) -> tuple[str, ...]:
    value = entry.get(key) or []
    if not isinstance(value, list):
        raise DdeError(
            "VALIDATION_FAILED",
            f"binding matrix field {key} must be a list",
            retryable=False,
            details={"row": row_id},
        )
    return tuple(str(item) for item in value)


def _layer(name: EvidenceLayerName, raw: object, *, row_id: str) -> BindingEvidence:
    if not isinstance(raw, dict):
        raise DdeError(
            "VALIDATION_FAILED",
            f"{row_id}: evidence layer {name.value} must be an object",
            retryable=False,
        )
    applicable = bool(raw.get("applicable"))
    try:
        status = EvidenceStatus(str(raw["status"]))
    except (KeyError, ValueError) as exc:
        raise DdeError(
            "VALIDATION_FAILED",
            f"{row_id}: invalid status for layer {name.value}",
            retryable=False,
        ) from exc
    return BindingEvidence(
        layer=name,
        applicable=applicable,
        status=status,
        implementation_refs=_seq(raw, "implementation_refs", row_id=row_id),
        test_refs=_seq(raw, "test_refs", row_id=row_id),
        evidence_refs=_seq(raw, "evidence_refs", row_id=row_id),
        note=str(raw.get("note", "")),
    )


def _row(entry: Mapping[str, object]) -> BindingRow:
    row_id = str(entry["id"])
    raw_layers = entry.get("layers")
    if not isinstance(raw_layers, dict):
        raise DdeError(
            "VALIDATION_FAILED",
            f"{row_id}: multidimensional layers are required",
            retryable=False,
        )
    layers = {
        name: _layer(name, raw_layers.get(name.value), row_id=row_id)
        for name in EvidenceLayerName
    }

    def opt(key: str) -> str | None:
        value = entry.get(key)
        return str(value) if isinstance(value, str) and value else None

    return BindingRow(
        id=row_id,
        region=str(entry["region"]),
        feature=str(entry["feature"]),
        visual_contract=str(entry["visual_contract"]),
        read_model=opt("read_model"),
        command=opt("command"),
        state_transition=opt("state_transition"),
        capability=opt("capability"),
        permission=opt("permission"),
        failure_states=_seq(entry, "failure_states", row_id=row_id),
        layers=layers,
        note=str(entry.get("note", "")),
    )


def load_matrix(root: Path) -> BindingMatrix:
    path = root / MATRIX_RELATIVE
    if not path.is_file():
        raise DdeError(
            "CONTEXT_INCOMPLETE",
            "frontend binding matrix is missing",
            retryable=False,
            details={"path": MATRIX_RELATIVE},
        )
    document = json.loads(path.read_text(encoding="utf-8"))
    regions = tuple(
        BindingRegion(
            id=str(item["id"]),
            title=str(item["title"]),
            specification=str(item["specification"]),
        )
        for item in document["regions"]
    )
    return BindingMatrix(
        version=int(document["matrix_version"]),
        authority=str(document["authority"]),
        closure_rule=str(document["closure_rule"]),
        regions=regions,
        rows=tuple(_row(item) for item in document["rows"]),
    )


def _path_part(ref: str) -> str:
    return ref.split("::", 1)[0]


def integrity_findings(matrix: BindingMatrix, root: Path) -> tuple[str, ...]:
    """Return every reason the ledger would be unsafe to trust."""
    findings: list[str] = []
    seen: set[str] = set()
    known_regions = {region.id for region in matrix.regions}
    if matrix.version < 2:
        findings.append("matrix_version must be >= 2 for multidimensional evidence")

    for row in matrix.rows:
        if row.id in seen:
            findings.append(f"{row.id}: duplicate row id")
        seen.add(row.id)
        if row.region not in known_regions:
            findings.append(f"{row.id}: unknown region {row.region!r}")
        if not row.visual_contract:
            findings.append(f"{row.id}: no visual contract recorded")
        if set(row.layers) != set(EvidenceLayerName):
            findings.append(f"{row.id}: does not declare all evidence layers")
        for name, layer in row.layers.items():
            if layer.applicable and layer.status is EvidenceStatus.NOT_APPLICABLE:
                findings.append(f"{row.id}/{name.value}: applicable but NOT_APPLICABLE")
            if (
                not layer.applicable
                and layer.status is not EvidenceStatus.NOT_APPLICABLE
            ):
                findings.append(
                    f"{row.id}/{name.value}: non-applicable layer has "
                    f"{layer.status.value}"
                )
            if not layer.applicable and not layer.note:
                findings.append(
                    f"{row.id}/{name.value}: non-applicability needs a reason"
                )
            if (
                layer.status
                in {
                    EvidenceStatus.TYPED_UNAVAILABLE,
                    EvidenceStatus.BLOCKED_EXTERNAL,
                }
                and not layer.note
            ):
                findings.append(
                    f"{row.id}/{name.value}: unavailable/blocker needs a reason"
                )

            for ref in (
                *layer.implementation_refs,
                *layer.test_refs,
                *layer.evidence_refs,
            ):
                if not (root / _path_part(ref)).exists():
                    findings.append(
                        f"{row.id}/{name.value}: evidence ref not found: {ref}"
                    )

            if layer.applicable and layer.status is EvidenceStatus.VERIFIED:
                if not layer.implementation_refs:
                    findings.append(
                        f"{row.id}/{name.value}: VERIFIED names no implementation"
                    )
                if not (layer.test_refs or layer.evidence_refs):
                    findings.append(
                        f"{row.id}/{name.value}: VERIFIED names no test/evidence"
                    )

        for name in (
            EvidenceLayerName.UI,
            EvidenceLayerName.WIRED,
            EvidenceLayerName.E2E,
            EvidenceLayerName.VISUAL,
        ):
            if not row.layer(name).applicable:
                findings.append(
                    f"{row.id}/{name.value}: golden visible controls require this layer"
                )

        if row.status is BindingStatus.VERIFIED:
            for layer in row.layers.values():
                if layer.applicable and layer.status is not EvidenceStatus.VERIFIED:
                    findings.append(
                        f"{row.id}: final VERIFIED with incomplete {layer.layer.value}"
                    )
    return tuple(findings)


def render_markdown(matrix: BindingMatrix) -> str:
    counts = {status: len(matrix.by_status(status)) for status in BindingStatus}
    lines = [
        "# DDE Frontend Studio — functional binding matrix",
        "",
        "<!-- GENERATED FILE. Edit `docs/truth/golden/frontend_binding_matrix.json` "
        "and run `uv run python -m scripts.render_binding_matrix`. -->",
        "",
        f"**Authority:** {matrix.authority}",
        "",
        f"**Closure rule:** {matrix.closure_rule}",
        "",
        "## Final ledger state",
        "",
        "| Final status | Rows |",
        "|---|---:|",
    ]
    for status in BindingStatus:
        lines.append(f"| `{status.value}` | {counts[status]} |")
    lines += [f"| **total** | **{len(matrix.rows)}** |", ""]

    lines += [
        "Final status is derived. It is never authored independently "
        "of the eight layers.",
        "`NOT_APPLICABLE` is legal only with an explicit reason in canonical JSON.",
        "",
    ]
    layer_headers = " | ".join(name.value for name in EvidenceLayerName)
    for region in matrix.regions:
        lines += [
            f"## {region.title}",
            "",
            f"Specification: `{region.specification}`",
            "",
            f"| ID | Feature | {layer_headers} | FINAL |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for row in matrix.rows_for(region.id):
            cells = " | ".join(
                f"`{row.layer(name).status.value}`" for name in EvidenceLayerName
            )
            lines.append(
                f"| {row.id} | {_cell(row.feature)} | {cells} | `{row.status.value}` |"
            )
        lines.append("")
        notes = [row for row in matrix.rows_for(region.id) if row.note]
        if notes:
            lines += ["Notes:", ""]
            for row in notes:
                lines.append(f"- **{row.id}** — {row.note}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _cell(value: str | None) -> str:
    return value.replace("|", "\\|") if value else "—"
