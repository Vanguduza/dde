from __future__ import annotations

from engine.context.repo import repo_root
from engine.studio.audit.dogfood import reconcile_frontend_studio
from engine.studio.binding_matrix import BindingStatus, load_matrix


def test_real_99_control_ledger_is_reconciled_without_inventing_audit_passes() -> None:
    root = repo_root()
    matrix = load_matrix(root)
    report = reconcile_frontend_studio(matrix, root=root)
    assert report.control_count == 99
    # The ledger's own derived counts, not a remembered snapshot of them.
    # These move whenever a control genuinely closes; the property under
    # test is that the reconciler reports what the ledger says rather than
    # inventing an audit pass for an unproven control.
    assert report.verified == len(matrix.by_status(BindingStatus.VERIFIED))
    assert report.bound == len(matrix.by_status(BindingStatus.BOUND))
    assert report.typed_unavailable == len(
        matrix.by_status(BindingStatus.TYPED_UNAVAILABLE)
    )
    assert report.unbound == len(matrix.by_status(BindingStatus.UNBOUND))
    assert (
        report.verified + report.bound + report.typed_unavailable + report.unbound
        == report.control_count
    )
    assert report.audit_assessment_count == 0
    assert report.disagreement_count == 0
    assert not any(
        item.finding_type == "LEDGER_INTEGRITY_FAILURE" for item in report.findings
    )
    assert (
        sum(item.finding_type == "GOLDEN_CONTROL_UNBOUND" for item in report.findings)
        == report.unbound
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
