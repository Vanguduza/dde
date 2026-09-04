"""DDE-069 code-backed preview runtime invariants."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from engine.contracts.frontend_mutation import FrontendMutation, Preconditions
from engine.contracts.pxg_node import PxgNode, SourceRef
from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError
from engine.studio.preview_runtime.prototype_html import PrototypeHtmlPreviewAdapter
from engine.studio.pxg.service import PxgGraph


class _Files:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = dict(files)

    def read(self, _workspace: Workspace, relative_path: str) -> bytes:
        if relative_path not in self.files:
            raise FileNotFoundError(relative_path)
        return self.files[relative_path]

    def write(self, _workspace: Workspace, relative_path: str, content: bytes) -> None:
        self.files[relative_path] = content


def _workspace() -> Workspace:
    now = datetime.now(UTC)
    return Workspace(
        workspace_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        mission_id=None,
        task_id=None,
        execution_environment_id=None,
        base_revision="a" * 40,
        current_revision="a" * 40,
        workspace_path="/isolated/candidate",
        policy={"purpose": "test"},
        status="READY",
        lock_version=1,
        created_at=now,
        updated_at=now,
    )


def _node(
    key: str,
    kind: str,
    *,
    parent: str | None = None,
    element_id: str | None = None,
    source_path: str = "prototypes/screens/checkout.html",
) -> PxgNode:
    now = datetime.now(UTC)
    attributes: dict[str, object] = {}
    if element_id:
        attributes["element_id"] = element_id
    if kind == "screen":
        attributes["route"] = "/checkout"
    return PxgNode(
        node_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        pxg_key=key,
        node_kind=kind,
        title=key,
        parent_key=parent,
        pxg_revision=1,
        source_refs=[SourceRef(path=source_path, symbol="Checkout")],
        attributes=attributes,
        provenance={},
        lock_version=1,
        created_at=now,
        updated_at=now,
    )


def _graph(*, source_path: str = "prototypes/screens/checkout.html") -> PxgGraph:
    return PxgGraph(
        revision=1,
        nodes=(
            _node("screens/checkout", "screen", source_path=source_path),
            _node(
                "screens/checkout#hero",
                "region",
                parent="screens/checkout",
                element_id="hero-1",
                source_path=source_path,
            ),
        ),
        edges=(),
    )


def _mutation() -> FrontendMutation:
    now = datetime.now(UTC)
    return FrontendMutation(
        mutation_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        candidate_id=uuid4(),
        sequence=1,
        operation="SET_PROPERTY",
        target_key="screens/checkout#hero",
        origin="INSPECTOR",
        status="APPLIED",
        payload={"property": "spacing", "value": "space6"},
        inverse={"property": "spacing", "value": "space2"},
        preconditions=Preconditions(
            pxg_revision=1,
            candidate_base_revision=1,
            effective_lock_hash="locks",
        ),
        refusal_code=None,
        refusal_detail=None,
        reverted_by=None,
        created_at=now,
        updated_at=now,
    )


def test_materialization_mutates_candidate_code_and_instruments_stable_identity() -> (
    None
):
    original = (
        b'<html><body><div data-dde-el="hero-1" data-dde-kind="layout" '
        b'style="padding: var(--space-2)">Hero</div></body></html>'
    )
    files = _Files({"prototypes/screens/checkout.html": original})
    adapter = PrototypeHtmlPreviewAdapter(files)  # type: ignore[arg-type]
    session_id = uuid4()

    result = adapter.materialize(
        workspace=_workspace(),
        graph=_graph(),
        history=(_mutation(),),
        screen_key="screens/checkout",
        preview_session_id=session_id,
    )

    candidate_source = files.files["prototypes/screens/checkout.html"].decode()
    preview = files.files[result.document_path].decode()
    assert candidate_source != original.decode()
    assert 'data-dde-spacing="space6"' in candidate_source
    assert "padding: var(--space-6)" in candidate_source
    assert 'data-dde-pxg-key="screens/checkout#hero"' in preview
    assert str(session_id) in preview
    assert result.content_hash == hashlib.sha256(candidate_source.encode()).hexdigest()
    assert result.route == "/checkout"
    assert result.instrumented_keys == ("screens/checkout#hero",)


def test_pxg_identity_survives_dom_reordering() -> None:
    first = (
        b'<html><body><div data-dde-el="hero-1">Hero</div>'
        b'<div data-dde-el="other">Other</div></body></html>'
    )
    second = (
        b'<html><body><div data-dde-el="other">Other</div>'
        b'<div data-dde-el="hero-1">Hero</div></body></html>'
    )
    for source in (first, second):
        files = _Files({"prototypes/screens/checkout.html": source})
        adapter = PrototypeHtmlPreviewAdapter(files)  # type: ignore[arg-type]
        result = adapter.materialize(
            workspace=_workspace(),
            graph=_graph(),
            history=(),
            screen_key="screens/checkout",
            preview_session_id=uuid4(),
        )
        preview = files.files[result.document_path].decode()
        hero_open = preview.split('data-dde-el="hero-1"', 1)[1].split(">", 1)[0]
        assert 'data-dde-pxg-key="screens/checkout#hero"' in hero_open


def test_non_prototype_source_fails_closed_instead_of_faking_live_html() -> None:
    files = _Files({})
    adapter = PrototypeHtmlPreviewAdapter(files)  # type: ignore[arg-type]
    with pytest.raises(DdeError) as excinfo:
        adapter.validate(
            graph=_graph(source_path="src/routes/Checkout.tsx"),
            history=(),
            screen_key="screens/checkout",
        )
    assert excinfo.value.error_code == "CONTEXT_INCOMPLETE"
    assert "runtime adapter" in excinfo.value.message
