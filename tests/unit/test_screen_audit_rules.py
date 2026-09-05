from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from engine.contracts.frontend_contract import FrontendContract, Obligation
from engine.contracts.pxg_edge import PxgEdge
from engine.contracts.pxg_node import PxgNode, SourceRef
from engine.studio.audit.rules import AuditComputation, reconcile
from engine.studio.pxg.service import PxgGraph
from tests.support.pxg_fixtures import node


def _contract(*obligations: Obligation) -> FrontendContract:
    now = datetime.now(UTC)
    return FrontendContract(
        contract_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        mission_id=uuid4(),
        contract_version=1,
        content_hash="a" * 64,
        status="ACTIVE",
        obligations=list(obligations),
        created_at=now,
        updated_at=now,
    )


def _obligation(
    key: str,
    *,
    dimension: str = "screen",
    applicability: str = "REQUIRED",
    decision_ref: str | None = None,
    verification_kinds: tuple[str, ...] = (),
) -> Obligation:
    return Obligation(
        obligation_id=uuid4(),
        dimension=dimension,
        pxg_key=key,
        statement=f"{key} must exist",
        requirement_refs=["REQ-1"],
        applicability=applicability,
        applicability_decision_ref=decision_ref,
        verification_kinds=list(verification_kinds),
    )


def _screen(
    key: str,
    *,
    bound: tuple[str, ...] = ("silhouette", "visual_critique"),
    attributes: dict[str, object] | None = None,
) -> PxgNode:
    values: dict[str, object] = {
        "bound_verification_kinds": list(bound),
        **(attributes or {}),
    }
    return node(key, "screen", attributes=values).model_copy(
        update={"source_refs": [SourceRef(path=f"src/{key}.tsx")]}
    )


def _graph(*nodes: PxgNode, edges: tuple[PxgEdge, ...] = ()) -> PxgGraph:
    return PxgGraph(revision=1, nodes=tuple(nodes), edges=edges)


def _edge(source: str, target: str) -> PxgEdge:
    now = datetime.now(UTC)
    return PxgEdge(
        edge_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        from_key=source,
        to_key=target,
        edge_kind="navigates_to",
        pxg_revision=1,
        attributes={},
        created_at=now,
        updated_at=now,
    )


def _types(result: AuditComputation) -> set[str]:
    return {item.finding_type for item in result.findings}


def test_no_contract_blocks_instead_of_fabricating_completeness() -> None:
    result = reconcile(None, _graph(_screen("screens/login")))
    assert result.summary_state == "BLOCKED"
    assert "FRONTEND_CONTRACT_UNAVAILABLE" in _types(result)
    assert result.screens[0].dimension_states["CONTRACT"] == "BLOCKED"


def test_required_screen_missing_is_blocking_failure() -> None:
    result = reconcile(_contract(_obligation("screens/checkout")), _graph())
    finding = next(
        item
        for item in result.findings
        if item.finding_type == "REQUIRED_SCREEN_MISSING"
    )
    assert finding.severity == "BLOCKING"
    assert finding.assessment_state == "FAIL"
    assert result.screens[0].implementation_state == "MISSING"


def test_missing_mandatory_visual_bindings_fail_closed() -> None:
    screen = _screen("screens/checkout", bound=("test",))
    result = reconcile(_contract(_obligation(screen.pxg_key)), _graph(screen))
    finding = next(
        item
        for item in result.findings
        if item.finding_type == "MANDATORY_VISUAL_BINDING_MISSING"
    )
    assert finding.severity == "BLOCKING"
    record = result.screens[0]
    assert record.dimension_states["VISUAL"] == "FAIL"
    assert record.dimension_states["VERIFICATION"] == "FAIL"


def test_bound_visual_checks_without_current_accepted_evidence_stay_unknown() -> None:
    screen = _screen("screens/checkout")
    result = reconcile(_contract(_obligation(screen.pxg_key)), _graph(screen))
    assert "MANDATORY_VISUAL_VERIFICATION_NOT_CURRENT" in _types(result)
    record = result.screens[0]
    assert record.dimension_states["VISUAL"] == "UNKNOWN"
    assert record.dimension_states["VERIFICATION"] == "UNKNOWN"


def test_current_mandatory_visual_evidence_can_pass_visual_dimension() -> None:
    screen = _screen("screens/checkout")
    child = node("screens/checkout#region", "region", parent=screen.pxg_key)
    result = reconcile(
        _contract(_obligation(screen.pxg_key)),
        _graph(screen, child),
        passing_verifications={
            screen.pxg_key: frozenset({"silhouette", "visual_critique"})
        },
    )
    record = result.screens[0]
    assert record.dimension_states["VISUAL"] == "PASS"
    assert record.dimension_states["VERIFICATION"] == "PASS"
    assert "MANDATORY_VISUAL_VERIFICATION_NOT_CURRENT" not in _types(result)


def test_unbound_visible_control_becomes_functional_finding() -> None:
    screen = _screen("screens/checkout")
    interaction = node(
        "screens/checkout#submit",
        "interaction",
        parent=screen.pxg_key,
        attributes={},
    )
    result = reconcile(
        _contract(_obligation(screen.pxg_key)),
        _graph(screen, interaction),
        passing_verifications={
            screen.pxg_key: frozenset({"silhouette", "visual_critique"})
        },
    )
    finding = next(
        item
        for item in result.findings
        if item.finding_type == "VISIBLE_CONTROL_UNBOUND"
    )
    assert finding.dimension == "FUNCTIONAL"
    assert finding.node_key == interaction.pxg_key


def test_destructive_control_without_confirmation_is_blocking() -> None:
    screen = _screen("screens/admin")
    interaction = node(
        "screens/admin#delete",
        "interaction",
        parent=screen.pxg_key,
        attributes={"command_ref": "admin.delete", "destructive": True},
    )
    result = reconcile(
        _contract(_obligation(screen.pxg_key)),
        _graph(screen, interaction),
        passing_verifications={
            screen.pxg_key: frozenset({"silhouette", "visual_critique"})
        },
    )
    finding = next(
        item
        for item in result.findings
        if item.finding_type == "DESTRUCTIVE_ACTION_NO_CONFIRMATION"
    )
    assert finding.severity == "BLOCKING"


def test_data_screen_missing_loading_empty_error_states_is_explicit() -> None:
    screen = _screen("screens/orders")
    binding = node("screens/orders#data", "data_binding", parent=screen.pxg_key)
    result = reconcile(
        _contract(_obligation(screen.pxg_key)),
        _graph(screen, binding),
        passing_verifications={
            screen.pxg_key: frozenset({"silhouette", "visual_critique"})
        },
    )
    assert "MANDATORY_DATA_STATE_MISSING" in _types(result)
    assert result.screens[0].dimension_states["STATE"] == "FAIL"


def test_deferred_obligation_without_durable_decision_is_blocking() -> None:
    result = reconcile(
        _contract(
            _obligation(
                "screens/later",
                applicability="DEFERRED_APPROVED",
                decision_ref=None,
            )
        ),
        _graph(),
    )
    finding = next(
        item
        for item in result.findings
        if item.finding_type == "DEFERRED_WITHOUT_DECISION"
    )
    assert finding.severity == "BLOCKING"


def test_dangling_navigation_and_orphan_parent_surface_as_drift() -> None:
    screen = _screen("screens/a")
    orphan = node("screens/a#lost", "component", parent="screens/missing")
    result = reconcile(
        _contract(_obligation(screen.pxg_key)),
        _graph(screen, orphan, edges=(_edge(screen.pxg_key, "screens/no-target"),)),
        passing_verifications={
            screen.pxg_key: frozenset({"silhouette", "visual_critique"})
        },
    )
    assert "ORPHAN_NODE" in _types(result)
    assert "DANGLING_NAVIGATION_TARGET" in _types(result)


def test_incremental_scope_emits_only_affected_screen_records() -> None:
    first = _screen("screens/a")
    second = _screen("screens/b")
    result = reconcile(
        _contract(_obligation(first.pxg_key), _obligation(second.pxg_key)),
        _graph(first, second),
        passing_verifications={
            first.pxg_key: frozenset({"silhouette", "visual_critique"}),
            second.pxg_key: frozenset({"silhouette", "visual_critique"}),
        },
        affected_keys=frozenset({"screens/b"}),
    )
    assert [item.pxg_key for item in result.screens] == ["screens/b"]
    assert all(item.pxg_key in {None, "screens/b"} for item in result.findings)
