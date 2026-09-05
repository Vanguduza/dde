"""DDE-069 self-audit reconciliation against the independent golden ledger.

The 99-control binding matrix and Screen Audit answer different questions.  This
module never mutates either one to make them agree: it validates the ledger,
projects its current gaps, and records disagreements when a real Screen Audit
assessment for the corresponding control is available.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from engine.studio.binding_matrix import (
    BindingMatrix,
    BindingStatus,
    integrity_findings,
)


@dataclass(frozen=True)
class DogfoodFinding:
    control_id: str | None
    finding_type: str
    severity: str
    detail: str
    ledger_status: str | None = None
    audit_state: str | None = None


@dataclass(frozen=True)
class DogfoodReport:
    matrix_version: int
    control_count: int
    verified: int
    bound: int
    typed_unavailable: int
    unbound: int
    audit_assessment_count: int
    findings: tuple[DogfoodFinding, ...]

    @property
    def disagreement_count(self) -> int:
        return sum(
            1
            for item in self.findings
            if item.finding_type == "AUDIT_LEDGER_DISAGREEMENT"
        )


def reconcile_frontend_studio(
    matrix: BindingMatrix,
    *,
    root: Path,
    audit_states: Mapping[str, str] | None = None,
) -> DogfoodReport:
    """Reconcile ledger integrity/gaps with independent Screen Audit states.

    ``audit_states`` is keyed by the golden control id and must come from a real
    Screen Audit projection (for example a PXG node whose stable identity carries
    that control id).  Absence is honest NOT_EVALUATED, not an inferred pass.
    """
    supplied = dict(audit_states or {})
    findings: list[DogfoodFinding] = []

    for detail in integrity_findings(matrix, root):
        findings.append(
            DogfoodFinding(
                control_id=_leading_control_id(detail),
                finding_type="LEDGER_INTEGRITY_FAILURE",
                severity="BLOCKING",
                detail=detail,
            )
        )

    for row in matrix.rows:
        if row.status is BindingStatus.UNBOUND:
            findings.append(
                DogfoodFinding(
                    control_id=row.id,
                    finding_type="GOLDEN_CONTROL_UNBOUND",
                    severity="ERROR",
                    detail=(
                        f"{row.feature}: one or more applicable evidence layers "
                        "are UNBOUND"
                    ),
                    ledger_status=row.status.value,
                )
            )
        elif row.status is BindingStatus.TYPED_UNAVAILABLE:
            findings.append(
                DogfoodFinding(
                    control_id=row.id,
                    finding_type="GOLDEN_CONTROL_BLOCKED_OR_UNAVAILABLE",
                    severity="WARNING",
                    detail=(
                        f"{row.feature}: capability is explicitly unavailable/"
                        "externally blocked"
                    ),
                    ledger_status=row.status.value,
                )
            )
        elif row.status is BindingStatus.BOUND:
            findings.append(
                DogfoodFinding(
                    control_id=row.id,
                    finding_type="GOLDEN_CONTROL_PARTIAL",
                    severity="INFO",
                    detail=(
                        f"{row.feature}: partially evidenced but not "
                        "closure-grade VERIFIED"
                    ),
                    ledger_status=row.status.value,
                )
            )

        audit_state = supplied.get(row.id)
        if audit_state is None:
            continue
        ledger_pass = row.status is BindingStatus.VERIFIED
        audit_pass = audit_state == "PASS"
        if ledger_pass != audit_pass:
            findings.append(
                DogfoodFinding(
                    control_id=row.id,
                    finding_type="AUDIT_LEDGER_DISAGREEMENT",
                    severity="BLOCKING" if ledger_pass and not audit_pass else "ERROR",
                    detail=(
                        f"Screen Audit says {audit_state} while binding ledger says "
                        f"{row.status.value}; reconcile evidence without forcing "
                        "either source"
                    ),
                    ledger_status=row.status.value,
                    audit_state=audit_state,
                )
            )

    counts = {status: len(matrix.by_status(status)) for status in BindingStatus}
    return DogfoodReport(
        matrix_version=matrix.version,
        control_count=len(matrix.rows),
        verified=counts[BindingStatus.VERIFIED],
        bound=counts[BindingStatus.BOUND],
        typed_unavailable=counts[BindingStatus.TYPED_UNAVAILABLE],
        unbound=counts[BindingStatus.UNBOUND],
        audit_assessment_count=len(supplied),
        findings=tuple(findings),
    )


def _leading_control_id(detail: str) -> str | None:
    token = detail.split(":", 1)[0].split("/", 1)[0]
    return token if "-" in token else None
