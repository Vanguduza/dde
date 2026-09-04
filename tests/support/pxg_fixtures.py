"""Builders for Project Experience Graph test fixtures."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from engine.contracts.pxg_node import PxgNode


def node(
    key: str,
    kind: str,
    *,
    title: str | None = None,
    parent: str | None = None,
    attributes: dict[str, object] | None = None,
    revision: int = 1,
) -> PxgNode:
    now = datetime.now(UTC)
    return PxgNode(
        node_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        pxg_key=key,
        node_kind=kind,
        title=title or key,
        parent_key=parent,
        pxg_revision=revision,
        source_refs=[],
        attributes=attributes or {},
        provenance={},
        lock_version=1,
        created_at=now,
        updated_at=now,
    )
