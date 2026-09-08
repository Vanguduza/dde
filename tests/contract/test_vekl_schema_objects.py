"""Schema-first Production VEKL boundary contracts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from engine.contracts.hook_ir import HookIR
from engine.contracts.project import Project
from engine.contracts.vekl_resource import VEKLResource
from engine.gateway.api import router
from engine.gateway.scopes import COMMAND_SCOPES, COMMAND_TARGET_TYPE


def test_project_kind_and_vekl_resource_are_closed_vocabularies() -> None:
    now = datetime.now(UTC)
    project = Project(
        project_id=uuid4(),
        tenant_id=uuid4(),
        slug="target",
        kind="TARGET_APPLICATION",
        created_at=now,
        updated_at=now,
    )
    assert project.kind == "TARGET_APPLICATION"
    with pytest.raises(ValidationError):
        project.model_copy(update={"kind": "MODEL_DECIDES"}, deep=True).__class__(
            **{**project.model_dump(), "kind": "MODEL_DECIDES"}
        )

    resource = VEKLResource(
        resource_id=uuid4(),
        tenant_id=project.tenant_id,
        project_id=project.project_id,
        resource_kind="PLUGIN",
        title="bundle metadata",
        publisher="publisher",
        revision="1.0.0",
        content_hash="a" * 64,
        source_trust="S3_VERIFIED_REGISTRY",
        reuse_class="SOURCE_REFERENCE_ONLY",
        lifecycle_state="METADATA_VERIFIED",
        activation_modes=["REFERENCE_ONLY"],
        exact_versions={"plugin": "1.0.0"},
        license_ids=["Apache-2.0"],
        provenance={"source": "registry", "hash_verified": True},
        required_capabilities=[],
        filesystem_scopes=[],
        network_scopes=[],
        secret_scopes=[],
        sandbox_requirements={},
        side_effect_class="PURE_READ",
        required_verifiers=[],
        stack_constraints={},
        truth_constraints={},
        freshness={"stale": False},
        budget={"tokens": 20},
        injection_findings=[],
        content_excerpt="metadata",
        created_at=now,
        updated_at=now,
    )
    assert resource.source_trust == "S3_VERIFIED_REGISTRY"
    assert resource.reuse_class == "SOURCE_REFERENCE_ONLY"
    with pytest.raises(ValidationError):
        VEKLResource.model_validate(
            {**resource.model_dump(), "source_trust": "POPULAR"}
        )


def test_hook_and_loop_require_explicit_bounds() -> None:
    hook = HookIR(
        hook_id="lint",
        hook_class="pre_commit",
        event="before_commit",
        matcher={},
        command=["ruff", "check"],
        capability_id=None,
        filesystem_scopes=["src/**"],
        network_scopes=[],
        secret_scopes=[],
        timeout_seconds=30,
        failure_policy="BLOCK",
        evidence_types=["command_result"],
    )
    assert hook.timeout_seconds == 30
    schema = json.loads(
        (Path("schemas/objects/bounded_loop_definition.json")).read_text()
    )
    assert schema["properties"]["max_cycles"]["minimum"] == 1
    assert schema["properties"]["max_steps"]["minimum"] == 1


def test_gateway_exposes_authorized_vekl_read_projection() -> None:
    paths = {getattr(route, "path", "") for route in router.routes}
    assert "/v1/missions/{mission_id}/vekl" in paths
    for command_type in (
        "vekl.resource.register",
        "vekl.resource.transition",
        "vekl.activation.prepare",
        "vekl.context.compile",
        "vekl.outcome.record",
    ):
        assert COMMAND_SCOPES[command_type] == "mission.control"
        assert COMMAND_TARGET_TYPE[command_type] == "mission"
