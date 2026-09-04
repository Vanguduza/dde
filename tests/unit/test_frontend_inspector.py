"""DDE-069 descriptor-driven Inspector projection."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from engine.contracts.frontend_candidate import FrontendCandidate
from engine.contracts.frontend_lock import FrontendLock
from engine.contracts.pxg_node import PxgNode, SourceRef
from engine.studio.inspector import build_descriptor
from engine.studio.pxg.service import PxgGraph


def _candidate() -> FrontendCandidate:
    now = datetime.now(UTC)
    return FrontendCandidate(
        candidate_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        mission_id=None,
        workspace_id=uuid4(),
        title="Current design",
        state="READY",
        origin="DIRECT_EDIT",
        base_pxg_revision=1,
        base_contract_version=1,
        scope_keys=["screens/checkout"],
        verification_run_id=None,
        provenance={},
        state_detail=None,
        superseded_by=None,
        promoted_at=None,
        lock_version=1,
        created_at=now,
        updated_at=now,
    )


def _node(
    key: str,
    kind: str,
    *,
    parent: str | None = None,
    attributes: dict[str, object] | None = None,
) -> PxgNode:
    now = datetime.now(UTC)
    return PxgNode(
        node_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        pxg_key=key,
        node_kind=kind,
        title="Hero" if key.endswith("#hero") else "Checkout",
        parent_key=parent,
        pxg_revision=1,
        source_refs=[
            SourceRef(path="prototypes/screens/checkout.html", symbol="Checkout")
        ],
        attributes=attributes or {},
        provenance={},
        lock_version=1,
        created_at=now,
        updated_at=now,
    )


def _graph() -> PxgGraph:
    return PxgGraph(
        revision=2,
        nodes=(
            _node(
                "screens/checkout",
                "screen",
                attributes={
                    "bound_verification_kinds": ["visual_critique", "silhouette"]
                },
            ),
            _node(
                "screens/checkout#hero",
                "region",
                parent="screens/checkout",
                attributes={"element_id": "hero-1", "spacing": "space2"},
            ),
        ),
        edges=(),
    )


def _style_lock() -> FrontendLock:
    now = datetime.now(UTC)
    return FrontendLock(
        lock_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        lock_kind="STYLE",
        scope_key="screens/checkout#hero",
        status="ACTIVE",
        reason="approved spacing is frozen",
        created_by=uuid4(),
        released_by=None,
        released_at=None,
        lock_version=1,
        created_at=now,
        updated_at=now,
    )


def test_descriptor_uses_real_token_catalogue_and_source_mapping() -> None:
    descriptor = build_descriptor(
        candidate=_candidate(),
        graph=_graph(),
        locks=[],
        pxg_key="screens/checkout#hero",
        stale=False,
    )
    assert descriptor.pxg_key == "screens/checkout#hero"
    assert descriptor.source_mapping == "VERIFIED"
    assert descriptor.source_path == "prototypes/screens/checkout.html"
    assert descriptor.element_id == "hero-1"
    assert descriptor.required_verification == ("silhouette", "visual_critique")

    spacing = next(
        item for item in descriptor.properties if item.property_name == "spacing"
    )
    assert spacing.value == "space2"
    assert spacing.computed_value == "8px"
    assert "space6" in spacing.legal_values
    assert spacing.mutation_operation == "SET_PROPERTY"
    assert spacing.writable is True
    assert spacing.preview_invalidation == ("PREVIEW", "VISUAL_VERIFICATION")


def test_operation_sensitive_lock_disables_write_without_erasing_descriptor() -> None:
    descriptor = build_descriptor(
        candidate=_candidate(),
        graph=_graph(),
        locks=[_style_lock()],
        pxg_key="screens/checkout#hero",
        stale=False,
    )
    spacing = next(
        item for item in descriptor.properties if item.property_name == "spacing"
    )
    assert spacing.writable is False
    assert "STYLE" in (spacing.lock_reason or "")
    assert "approved spacing is frozen" in (spacing.lock_reason or "")
    assert spacing.value == "space2"


def test_stale_candidate_is_readable_but_not_writable() -> None:
    descriptor = build_descriptor(
        candidate=_candidate(),
        graph=_graph(),
        locks=[],
        pxg_key="screens/checkout#hero",
        stale=True,
    )
    assert descriptor.stale is True
    assert all(item.writable is False for item in descriptor.properties)
