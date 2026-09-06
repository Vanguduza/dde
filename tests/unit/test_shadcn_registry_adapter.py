from __future__ import annotations

import hashlib
import json

import pytest

from engine.core.errors import DdeError
from engine.studio.source.adapters import SourceQueryContext
from engine.studio.source.shadcn_registry import (
    PublicShadcnRegistryAdapter,
    RegistrySpec,
)


def _spec() -> RegistrySpec:
    return RegistrySpec(
        provider_key="example",
        display_name="Example Registry",
        index_url="https://registry.example/r/registry.json",
        item_url_template="https://registry.example/r/{name}.json",
        license_state="OPEN_REUSE",
        license_ids=("MIT",),
        license_evidence_uri="https://registry.example/LICENSE",
    )


def _index() -> bytes:
    return json.dumps(
        {
            "name": "example",
            "homepage": "https://registry.example",
            "items": [
                {
                    "name": "button",
                    "type": "registry:ui",
                    "title": "Button",
                    "description": "Accessible action control",
                    "dependencies": ["class-variance-authority"],
                    "registryDependencies": ["utils"],
                },
                {
                    "name": "checkout-shell",
                    "type": "registry:block",
                    "title": "Checkout Shell",
                    "description": "Dense order checkout surface",
                },
            ],
        }
    ).encode()


def _item(name: str, *, returned_name: str | None = None) -> bytes:
    return json.dumps(
        {
            "name": returned_name or name,
            "type": "registry:ui",
            "title": name.title(),
            "dependencies": ["motion"],
            "files": [
                {
                    "path": f"registry/{name}.tsx",
                    "type": "registry:ui",
                    "content": f"export const {name.replace('-', '_')} = 1",
                }
            ],
        },
        sort_keys=True,
    ).encode()


class FakeFetcher:
    def __init__(self, responses: dict[str, bytes]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, int]] = []

    async def __call__(self, url: str, max_bytes: int) -> bytes:
        self.calls.append((url, max_bytes))
        if url not in self.responses:
            raise DdeError("PROVIDER_UNAVAILABLE", "not found")
        return self.responses[url]


@pytest.mark.asyncio
async def test_public_registry_search_inspect_fetch_is_read_only_and_hash_pinned() -> (
    None
):
    spec = _spec()
    item_bytes = _item("button")
    fetcher = FakeFetcher(
        {
            spec.index_url: _index(),
            spec.item_url("button"): item_bytes,
        }
    )
    adapter = PublicShadcnRegistryAdapter(spec, fetcher=fetcher, cache={})
    context = SourceQueryContext(
        tenant_id=__import__("uuid").uuid4(), project_id=__import__("uuid").uuid4()
    )

    health = await adapter.health(context)
    assert health.status == "AVAILABLE"
    assert health.item_count == 2

    searched = await adapter.search(context, "button")
    assert [item.provider_artifact_key for item in searched] == ["button"]
    assert searched[0].license_state == "OPEN_REUSE"
    assert searched[0].license_ids == ("MIT",)
    assert searched[0].retrieval_state == "INDEXED"
    assert searched[0].dependency_manifest == ("class-variance-authority", "utils")

    inspected = await adapter.inspect(context, "checkout-shell")
    assert inspected is not None
    assert inspected.artifact_kind == "TEMPLATE"
    assert inspected.retrieval_state == "INSPECTED"

    fetched = await adapter.fetch(context, "button")
    assert fetched is not None
    assert fetched.content == item_bytes
    assert fetched.candidate.retrieval_state == "FETCHED"
    assert fetched.candidate.content_hash == hashlib.sha256(item_bytes).hexdigest()
    assert fetched.candidate.dependency_manifest == ("motion",)

    # One index read is shared by health/search/inspect/fetch for this adapter.
    assert [url for url, _ in fetcher.calls].count(spec.index_url) == 1


@pytest.mark.asyncio
async def test_fetch_refuses_item_identity_drift() -> None:
    spec = _spec()
    fetcher = FakeFetcher(
        {
            spec.index_url: _index(),
            spec.item_url("button"): _item("button", returned_name="other"),
        }
    )
    adapter = PublicShadcnRegistryAdapter(spec, fetcher=fetcher, cache={})
    context = SourceQueryContext(
        tenant_id=__import__("uuid").uuid4(), project_id=__import__("uuid").uuid4()
    )
    with pytest.raises(DdeError) as excinfo:
        await adapter.fetch(context, "button")
    assert excinfo.value.error_code == "EVIDENCE_CONFLICT"


@pytest.mark.asyncio
async def test_fetch_will_not_invent_an_item_absent_from_the_index() -> None:
    spec = _spec()
    fetcher = FakeFetcher({spec.index_url: _index()})
    adapter = PublicShadcnRegistryAdapter(spec, fetcher=fetcher, cache={})
    context = SourceQueryContext(
        tenant_id=__import__("uuid").uuid4(), project_id=__import__("uuid").uuid4()
    )
    assert await adapter.fetch(context, "not-indexed") is None
    assert len(fetcher.calls) == 1


def test_registry_spec_is_https_only_and_requires_an_item_placeholder() -> None:
    with pytest.raises(ValueError):
        RegistrySpec(
            provider_key="bad",
            display_name="Bad",
            index_url="http://registry.example/index.json",
            item_url_template="https://registry.example/r/{name}.json",
        )
    with pytest.raises(ValueError):
        RegistrySpec(
            provider_key="bad",
            display_name="Bad",
            index_url="https://registry.example/index.json",
            item_url_template="https://registry.example/r/item.json",
        )


@pytest.mark.asyncio
async def test_unknown_license_stays_unknown_for_admission_to_decide_later() -> None:
    spec = RegistrySpec(
        provider_key="unknown-license",
        display_name="Unknown License Registry",
        index_url="https://registry.example/r/registry.json",
        item_url_template="https://registry.example/r/{name}.json",
    )
    fetcher = FakeFetcher({spec.index_url: _index()})
    adapter = PublicShadcnRegistryAdapter(spec, fetcher=fetcher, cache={})
    context = SourceQueryContext(
        tenant_id=__import__("uuid").uuid4(), project_id=__import__("uuid").uuid4()
    )
    result = await adapter.search(context, "button")
    assert result[0].license_state == "UNKNOWN"
    assert result[0].license_ids == ()
