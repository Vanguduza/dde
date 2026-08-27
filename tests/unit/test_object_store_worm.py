"""Chapter 17.5 WORM at the object-store mediator (pure; no PostgreSQL)."""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import uuid4

import pytest

from engine.core.errors import DdeError
from engine.object_store.scope import (
    WORM_CONTROL,
    ArtifactObjectStore,
    ScopeViolationError,
    storage_key_for_artifact,
)


def test_object_store_refuses_evidence_linked_delete() -> None:
    tenant_id, project_id = uuid4(), uuid4()
    store = ArtifactObjectStore()
    key = storage_key_for_artifact(
        tenant_id=tenant_id, project_id=project_id, content_hash="abc"
    )
    with pytest.raises(DdeError) as excinfo:
        store.delete(
            tenant_id=tenant_id,
            project_id=project_id,
            key=key,
            evidence_linked=True,
        )
    assert excinfo.value.error_code == "POLICY_DENIED"
    assert excinfo.value.details is not None
    assert excinfo.value.details["control"] == WORM_CONTROL


def test_object_store_delete_still_enforces_scope() -> None:
    store = ArtifactObjectStore()
    with pytest.raises(ScopeViolationError):
        store.delete(
            tenant_id=uuid4(),
            project_id=uuid4(),
            key="artifacts/other/other/abc",
            evidence_linked=True,
        )


def test_dr_package_does_not_import_redis() -> None:
    """Ch.17.5: Redis is disposable; the drill must not treat it as a source."""
    forbidden = ("redis", "redis.asyncio")
    dr_root = Path(__file__).resolve().parents[2] / "engine" / "dr"
    for path in dr_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            for name in names:
                assert not any(
                    name == item or name.startswith(f"{item}.") for item in forbidden
                ), path
