"""The DDE-069 functional binding ledger.

`docs/truth/golden/frontend_binding_matrix.json` holds one row per
meaningful control in the AD-035 golden Frontend Studio. This module
loads it, enforces its integrity rules, and renders the human-readable
`docs/truth/FRONTEND_STUDIO_BINDING_MATRIX.md`.

The point of the ledger is that a control cannot quietly become theatre.
A row claiming `BOUND` must name production code that exists; a row
claiming `VERIFIED` must additionally name tests that exist. Those claims
are checked mechanically, so the matrix cannot drift ahead of the code.
"""

from __future__ import annotations

import json
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
    implementation_refs: tuple[str, ...]
    tests: tuple[str, ...]
    status: BindingStatus
    note: str


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


def _row(entry: dict[str, object]) -> BindingRow:
    def opt(key: str) -> str | None:
        value = entry.get(key)
        return str(value) if isinstance(value, str) and value else None

    def seq(key: str) -> tuple[str, ...]:
        value = entry.get(key) or []
        if not isinstance(value, list):
            raise DdeError(
                "VALIDATION_FAILED",
                f"binding matrix field {key} must be a list",
                retryable=False,
                details={"row": str(entry.get("id"))},
            )
        return tuple(str(item) for item in value)

    return BindingRow(
        id=str(entry["id"]),
        region=str(entry["region"]),
        feature=str(entry["feature"]),
        visual_contract=str(entry["visual_contract"]),
        read_model=opt("read_model"),
        command=opt("command"),
        state_transition=opt("state_transition"),
        capability=opt("capability"),
        permission=opt("permission"),
        failure_states=seq("failure_states"),
        implementation_refs=seq("implementation_refs"),
        tests=seq("tests"),
        status=BindingStatus(str(entry["status"])),
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
    rows = tuple(_row(item) for item in document["rows"])
    return BindingMatrix(
        version=int(document["matrix_version"]),
        authority=str(document["authority"]),
        closure_rule=str(document["closure_rule"]),
        regions=regions,
        rows=rows,
    )


def integrity_findings(matrix: BindingMatrix, root: Path) -> tuple[str, ...]:
    """Structural rules the ledger must satisfy to be worth trusting."""
    findings: list[str] = []
    seen: set[str] = set()
    known_regions = {region.id for region in matrix.regions}

    for row in matrix.rows:
        if row.id in seen:
            findings.append(f"{row.id}: duplicate row id")
        seen.add(row.id)
        if row.region not in known_regions:
            findings.append(f"{row.id}: unknown region {row.region!r}")
        if not row.visual_contract:
            findings.append(f"{row.id}: no visual contract recorded")

        if row.status in (BindingStatus.BOUND, BindingStatus.VERIFIED):
            if not row.read_model and not row.command:
                findings.append(
                    f"{row.id}: status {row.status.value} with neither a read "
                    "model nor a command"
                )
            if not row.implementation_refs:
                findings.append(
                    f"{row.id}: status {row.status.value} names no implementation_refs"
                )
            for ref in row.implementation_refs:
                if not (root / _path_part(ref)).exists():
                    findings.append(f"{row.id}: implementation ref not found: {ref}")

        if row.status is BindingStatus.VERIFIED:
            if not row.tests:
                findings.append(f"{row.id}: status VERIFIED names no tests")
            for ref in row.tests:
                if not (root / _path_part(ref)).exists():
                    findings.append(f"{row.id}: test ref not found: {ref}")

        if row.status is BindingStatus.TYPED_UNAVAILABLE and not row.note:
            findings.append(
                f"{row.id}: TYPED_UNAVAILABLE without a note explaining why "
                "the capability is absent"
            )
    return tuple(findings)


def _path_part(ref: str) -> str:
    """Refs may be `path` or `path::symbol`; only the path is checked."""
    return ref.split("::", 1)[0]


def render_markdown(matrix: BindingMatrix) -> str:
    counts = {status: len(matrix.by_status(status)) for status in BindingStatus}
    lines: list[str] = [
        "# DDE Frontend Studio — functional binding matrix",
        "",
        "<!-- GENERATED FILE. Edit "
        f"`{MATRIX_RELATIVE}` and run "
        "`uv run python -m scripts.render_binding_matrix`. -->",
        "",
        f"**Authority:** {matrix.authority}",
        "",
        f"**Closure rule:** {matrix.closure_rule}",
        "",
        "## Ledger state",
        "",
        "| Status | Rows |",
        "|---|---:|",
    ]
    for status in BindingStatus:
        lines.append(f"| `{status.value}` | {counts[status]} |")
    lines += [f"| **total** | **{len(matrix.rows)}** |", ""]

    for region in matrix.regions:
        rows = matrix.rows_for(region.id)
        lines += [
            f"## {region.title}",
            "",
            f"Specification: `{region.specification}`",
            "",
            "| ID | Feature | Visual contract | Read model | Command | "
            "State transition | Capability | Permission | Failure states | "
            "Implementation | Tests | Status |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for row in rows:
            lines.append(
                "| {id} | {feature} | {visual} | {read} | {command} | "
                "{transition} | {capability} | {permission} | {failures} | "
                "{impl} | {tests} | `{status}` |".format(
                    id=row.id,
                    feature=_cell(row.feature),
                    visual=_cell(row.visual_contract),
                    read=_code(row.read_model),
                    command=_code(row.command),
                    transition=_cell(row.state_transition),
                    capability=_code(row.capability),
                    permission=_cell(row.permission),
                    failures=" ".join(f"`{item}`" for item in row.failure_states)
                    or "—",
                    impl=_refs(row.implementation_refs),
                    tests=_refs(row.tests),
                    status=row.status.value,
                )
            )
        lines.append("")
        notes = [row for row in rows if row.note]
        if notes:
            lines.append("Notes:")
            lines.append("")
            for row in notes:
                lines.append(f"- **{row.id}** — {row.note}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _cell(value: str | None) -> str:
    return value.replace("|", "\\|") if value else "—"


def _code(value: str | None) -> str:
    return f"`{value}`" if value else "—"


def _refs(refs: tuple[str, ...]) -> str:
    return " ".join(f"`{ref}`" for ref in refs) if refs else "—"
