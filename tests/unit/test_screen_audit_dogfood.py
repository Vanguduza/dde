from __future__ import annotations

from engine.context.repo import repo_root
from engine.studio.audit.dogfood import reconcile_frontend_studio
from engine.studio.binding_matrix import BindingStatus, load_matrix


def test_real_99_control_ledger_is_reconciled_without_inventing_audit_passes() -> None:
    root = repo_root()
    matrix = load_matrix(root)
    report = reconcile_frontend_studio(matrix, root=root)
    assert report.control_count == 99
    assert report.verified == 5
    assert report.bound == 23
    assert report.typed_unavailable == 5
    assert report.unbound == 66
    assert report.audit_assessment_count == 0
    assert report.disagreement_count == 0
    assert not any(
        item.finding_type == "LEDGER_INTEGRITY_FAILURE" for item in report.findings
    )
    assert (
        sum(item.finding_type == "GOLDEN_CONTROL_UNBOUND" for item in report.findings)
        == 66
    )


def test_disagreement_is_recorded_instead_of_forcing_sources_to_agree() -> None:
    root = repo_root()
    matrix = load_matrix(root)
    verified = next(row for row in matrix.rows if row.status is BindingStatus.VERIFIED)
    partial = next(row for row in matrix.rows if row.status is BindingStatus.BOUND)
    report = reconcile_frontend_studio(
        matrix,
        root=root,
        audit_states={verified.id: "FAIL", partial.id: "PASS"},
    )
    disagreements = [
        item
        for item in report.findings
        if item.finding_type == "AUDIT_LEDGER_DISAGREEMENT"
    ]
    assert {item.control_id for item in disagreements} == {verified.id, partial.id}
    assert (
        next(item for item in disagreements if item.control_id == verified.id).severity
        == "BLOCKING"
    )
    assert (
        next(item for item in disagreements if item.control_id == partial.id).severity
        == "ERROR"
    )
