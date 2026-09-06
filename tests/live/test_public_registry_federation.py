"""Opt-in live certification for DDE-069 public registry federation."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from engine.studio.source.adapters import SourceQueryContext
from engine.studio.source.shadcn_registry import (
    ACETERNITY_SPEC,
    MAGIC_UI_SPEC,
    REUI_SPEC,
    SHADCN_SPEC,
    PublicShadcnRegistryAdapter,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("DDE_LIVE_PUBLIC_REGISTRIES", "").strip().lower()
    not in {"1", "true", "yes", "on"},
    reason="public registry certification is opt-in",
)

CASES = (
    (SHADCN_SPEC, "button"),
    (REUI_SPEC, "alert"),
    (MAGIC_UI_SPEC, "magic-card"),
    (ACETERNITY_SPEC, "grid"),
)


@pytest.mark.asyncio
async def test_public_registry_federation_is_live_and_hash_pinned() -> None:
    context = SourceQueryContext(tenant_id=uuid4(), project_id=uuid4())
    evidence: dict[str, object] = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "transport": "dde.shadcn-registry-http/1",
        "providers": [],
    }
    for spec, item_name in CASES:
        adapter = PublicShadcnRegistryAdapter(spec, cache={})
        health = await adapter.health(context)
        assert health.status == "AVAILABLE", (spec.provider_key, health.detail)
        searched = await adapter.search(context, item_name)
        assert any(row.provider_artifact_key == item_name for row in searched)
        inspected = await adapter.inspect(context, item_name)
        assert inspected is not None
        fetched = await adapter.fetch(context, item_name)
        assert fetched is not None and fetched.content is not None
        observed = hashlib.sha256(fetched.content).hexdigest()
        assert fetched.candidate.content_hash == observed
        assert fetched.candidate.retrieval_state == "FETCHED"
        evidence["providers"].append(
            {
                "provider_key": spec.provider_key,
                "index_url": spec.index_url,
                "item": item_name,
                "item_count": health.item_count,
                "content_hash": observed,
                "size_bytes": len(fetched.content),
                "license_state": fetched.candidate.license_state,
                "license_ids": list(fetched.candidate.license_ids),
            }
        )
    destination = os.environ.get("DDE_LIVE_PUBLIC_REGISTRY_EVIDENCE", "").strip()
    if destination:
        Path(destination).write_text(
            json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8"
        )
