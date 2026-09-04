"""DDE-069 binding-ledger honesty and drift tests.

The golden ledger is multidimensional: backend implementation evidence cannot
certify a missing React control, production binding or workbench E2E flow.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from engine.context.repo import repo_root
from engine.core.errors import DdeError
from engine.studio.binding_matrix import (
    MATRIX_RELATIVE,
    RENDERED_RELATIVE,
    BindingStatus,
    EvidenceLayerName,
    EvidenceStatus,
    integrity_findings,
    load_matrix,
    render_markdown,
)

SCHEMA_RELATIVE = "schemas/design/frontend_binding_matrix.schema.json"


def test_registry_matches_json_schema() -> None:
    root = repo_root()
    document = json.loads((root / MATRIX_RELATIVE).read_text(encoding="utf-8"))
    schema = json.loads((root / SCHEMA_RELATIVE).read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(document)


def test_registry_loads_and_satisfies_integrity_rules() -> None:
    root = repo_root()
    matrix = load_matrix(root)
    assert len(matrix.rows) == 99
    assert matrix.version == 2
    assert integrity_findings(matrix, root) == ()


def test_rendered_markdown_is_in_sync_with_registry() -> None:
    root = repo_root()
    rendered = render_markdown(load_matrix(root))
    current = (root / RENDERED_RELATIVE).read_text(encoding="utf-8")
    assert current == rendered, (
        f"{RENDERED_RELATIVE} is stale; run "
        "`uv run python -m scripts.render_binding_matrix`"
    )


def test_every_golden_region_and_layer_is_present() -> None:
    matrix = load_matrix(repo_root())
    expected_regions = {
        "global_top_bar",
        "app_rail_and_explorer",
        "orchestrator_card",
        "canvas_toolbar",
        "canvas",
        "frontend_chat",
        "candidate_dock",
        "source_blend",
        "inspector",
        "status_bar",
    }
    assert {region.id for region in matrix.regions} == expected_regions
    for region in matrix.regions:
        assert matrix.rows_for(region.id)
    for row in matrix.rows:
        assert set(row.layers) == set(EvidenceLayerName)


def test_backend_only_chat_cannot_claim_final_verified() -> None:
    matrix = load_matrix(repo_root())
    row = next(item for item in matrix.rows if item.id == "CH-01")
    assert row.layer(EvidenceLayerName.DOMAIN).status is EvidenceStatus.VERIFIED
    assert row.layer(EvidenceLayerName.COMMAND).status is EvidenceStatus.VERIFIED
    assert row.layer(EvidenceLayerName.UI).status is EvidenceStatus.UNBOUND
    assert row.layer(EvidenceLayerName.WIRED).status is EvidenceStatus.UNBOUND
    assert row.layer(EvidenceLayerName.E2E).status is EvidenceStatus.UNBOUND
    assert row.status is BindingStatus.UNBOUND


def test_backend_only_inspector_mutation_cannot_claim_final_verified() -> None:
    matrix = load_matrix(repo_root())
    row = next(item for item in matrix.rows if item.id == "IN-10")
    assert row.layer(EvidenceLayerName.COMMAND).status is EvidenceStatus.VERIFIED
    assert row.layer(EvidenceLayerName.UI).status is EvidenceStatus.UNBOUND
    assert row.layer(EvidenceLayerName.WIRED).status is EvidenceStatus.UNBOUND
    assert row.status is BindingStatus.UNBOUND


def test_design_gateway_is_distinct_from_certified_design_transport() -> None:
    matrix = load_matrix(repo_root())
    row = next(item for item in matrix.rows if item.id == "CT-06")
    assert row.layer(EvidenceLayerName.DOMAIN).status is EvidenceStatus.VERIFIED
    assert (
        row.layer(EvidenceLayerName.COMMAND).status is EvidenceStatus.TYPED_UNAVAILABLE
    )
    assert row.layer(EvidenceLayerName.E2E).status is EvidenceStatus.BLOCKED_EXTERNAL
    assert (
        row.status is BindingStatus.UNBOUND
    )  # UI is not wired to provider status/Gateway.


def test_final_verified_is_derived_from_every_applicable_layer() -> None:
    matrix = load_matrix(repo_root())
    verified = [row for row in matrix.rows if row.status is BindingStatus.VERIFIED]
    assert verified, (
        "the ledger should still be capable of proving bounded local UI facts"
    )
    for row in verified:
        assert all(
            layer.status is EvidenceStatus.VERIFIED
            for layer in row.layers.values()
            if layer.applicable
        ), row.id


def test_visible_control_layers_are_never_declared_not_applicable() -> None:
    matrix = load_matrix(repo_root())
    mandatory = {
        EvidenceLayerName.UI,
        EvidenceLayerName.WIRED,
        EvidenceLayerName.E2E,
        EvidenceLayerName.VISUAL,
    }
    for row in matrix.rows:
        for name in mandatory:
            assert row.layer(name).applicable, f"{row.id}/{name.value}"


def test_non_applicability_is_explicit_and_explained() -> None:
    matrix = load_matrix(repo_root())
    for row in matrix.rows:
        for layer in row.layers.values():
            if not layer.applicable:
                assert layer.status is EvidenceStatus.NOT_APPLICABLE
                assert layer.note.strip(), f"{row.id}/{layer.layer.value}"


def test_verified_layers_name_real_implementation_and_test_or_evidence() -> None:
    root = repo_root()
    matrix = load_matrix(root)
    for row in matrix.rows:
        for layer in row.layers.values():
            if layer.status is not EvidenceStatus.VERIFIED:
                continue
            assert layer.implementation_refs, f"{row.id}/{layer.layer.value}"
            assert layer.test_refs or layer.evidence_refs, (
                f"{row.id}/{layer.layer.value}"
            )
            for ref in (
                *layer.implementation_refs,
                *layer.test_refs,
                *layer.evidence_refs,
            ):
                assert (root / ref.split("::", 1)[0]).exists(), f"{row.id}: {ref}"


def test_final_status_is_not_authored_in_canonical_rows() -> None:
    document = json.loads((repo_root() / MATRIX_RELATIVE).read_text(encoding="utf-8"))
    assert all("status" not in row for row in document["rows"])


def test_row_ids_are_unique_and_every_row_has_visual_contract() -> None:
    matrix = load_matrix(repo_root())
    ids = [row.id for row in matrix.rows]
    assert len(ids) == len(set(ids)) == 99
    assert all(row.visual_contract.strip() for row in matrix.rows)


def test_missing_registry_is_refused_not_defaulted(tmp_path: Path) -> None:
    with pytest.raises(DdeError) as excinfo:
        load_matrix(tmp_path)
    assert excinfo.value.error_code == "CONTEXT_INCOMPLETE"
