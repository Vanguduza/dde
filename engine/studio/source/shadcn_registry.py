"""Governed read-only adapter for public shadcn-compatible registries.

DDE-069 Source Intelligence must not depend on one commercial aggregator.
This module treats a shadcn registry as a *source*, never an installer:
index/search/inspect/fetch are allowed, while install, publish and writes to
accepted project state are structurally absent. Exact fetched JSON bytes are
returned to SourceIntelligenceService, which hashes/stores/admission-checks
them before any reusable candidate can exist.

The network boundary is intentionally narrow:
- HTTPS only;
- configured hosts only, including after redirects;
- JSON content only;
- bounded index/item sizes;
- registry item names must come from the fetched index;
- no scripts or package-manager commands are executed.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final

from engine.core.errors import DdeError
from engine.studio.source.adapters import (
    FetchedSource,
    SourceCandidate,
    SourceHealth,
    SourceQueryContext,
)

INDEX_MAX_BYTES: Final = 3 * 1024 * 1024
ITEM_MAX_BYTES: Final = 2 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS: Final = 15.0
DEFAULT_CACHE_TTL_SECONDS: Final = 300.0
DEFAULT_MAX_RESULTS: Final = 200
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@/+-]{0,199}$")


@dataclass(frozen=True)
class RegistrySpec:
    provider_key: str
    display_name: str
    index_url: str
    item_url_template: str
    license_state: str = "UNKNOWN"
    license_ids: tuple[str, ...] = ()
    license_evidence_uri: str | None = None
    framework: str = "react"
    max_results: int = DEFAULT_MAX_RESULTS

    def __post_init__(self) -> None:
        if "{name}" not in self.item_url_template:
            raise ValueError("item_url_template must contain {name}")
        for value in (
            self.index_url,
            self.item_url_template.replace("{name}", "probe"),
        ):
            parsed = urllib.parse.urlparse(value)
            if parsed.scheme != "https" or not parsed.hostname:
                raise ValueError("public registry endpoints must be HTTPS URLs")

    @property
    def allowed_hosts(self) -> frozenset[str]:
        values = (self.index_url, self.item_url_template.replace("{name}", "probe"))
        return frozenset(
            host
            for value in values
            if (host := urllib.parse.urlparse(value).hostname) is not None
        )

    def item_url(self, name: str) -> str:
        if not _NAME_RE.fullmatch(name):
            raise DdeError(
                "PROVIDER_ERROR",
                "registry index returned an invalid item name",
                retryable=False,
                details={"provider": self.provider_key, "item_name": name},
            )
        safe = urllib.parse.quote(name, safe="@/._+-")
        return self.item_url_template.format(name=safe)


@dataclass(frozen=True)
class RegistryIndex:
    registry_name: str | None
    homepage: str | None
    items: tuple[Mapping[str, object], ...]


FetchBytes = Callable[[str, int], Awaitable[bytes]]
CacheValue = tuple[float, RegistryIndex]
IndexCache = dict[str, CacheValue]
_INDEX_CACHE: IndexCache = {}


class PublicShadcnRegistryAdapter:
    """Provider-specific instance of the generic public-registry boundary."""

    def __init__(
        self,
        spec: RegistrySpec,
        *,
        fetcher: FetchBytes | None = None,
        cache: IndexCache | None = None,
        clock: Callable[[], float] | None = None,
        cache_ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        self.spec = spec
        self.provider_key = spec.provider_key
        self._fetcher = fetcher or self._fetch
        self._cache = _INDEX_CACHE if cache is None else cache
        self._clock = clock or time.monotonic
        self._cache_ttl_seconds = cache_ttl_seconds
        self._index_lock = asyncio.Lock()

    async def health(self, context: SourceQueryContext) -> SourceHealth:
        del context
        try:
            index = await self._index()
        except DdeError as exc:
            return SourceHealth(
                "UNAVAILABLE",
                ("search", "inspect", "fetch", "license", "provenance"),
                f"{self.spec.display_name} registry unavailable: {exc.message}",
            )
        return SourceHealth(
            "AVAILABLE",
            ("search", "inspect", "fetch", "license", "provenance"),
            f"public read-only registry; {len(index.items)} indexed item(s)",
            len(index.items),
        )

    async def search(
        self, context: SourceQueryContext, query: str
    ) -> tuple[SourceCandidate, ...]:
        del context
        needle = query.strip().lower()
        index = await self._index()
        result: list[SourceCandidate] = []
        for item in index.items:
            candidate = self._candidate(item, index=index, retrieval_state="INDEXED")
            if candidate is None:
                continue
            haystack = " ".join(
                (
                    candidate.provider_artifact_key,
                    candidate.title,
                    str(candidate.metadata.get("description") or ""),
                    str(candidate.metadata.get("registry_type") or ""),
                )
            ).lower()
            if needle and needle not in haystack:
                continue
            result.append(candidate)
            if len(result) >= self.spec.max_results:
                break
        return tuple(result)

    async def inspect(
        self, context: SourceQueryContext, provider_artifact_key: str
    ) -> SourceCandidate | None:
        del context
        index = await self._index()
        item = self._find(index, provider_artifact_key)
        if item is None:
            return None
        candidate = self._candidate(item, index=index, retrieval_state="INSPECTED")
        return candidate

    async def fetch(
        self, context: SourceQueryContext, provider_artifact_key: str
    ) -> FetchedSource | None:
        del context
        index = await self._index()
        indexed = self._find(index, provider_artifact_key)
        if indexed is None:
            return None
        url = self.spec.item_url(provider_artifact_key)
        raw = await self._fetcher(url, ITEM_MAX_BYTES)
        payload = _json_object(raw, provider=self.provider_key, role="registry item")
        returned_name = payload.get("name")
        if returned_name != provider_artifact_key:
            raise DdeError(
                "EVIDENCE_CONFLICT",
                "registry item payload identity does not match the indexed item",
                retryable=False,
                details={
                    "provider": self.provider_key,
                    "requested": provider_artifact_key,
                    "returned": returned_name,
                },
            )
        candidate = self._candidate(payload, index=index, retrieval_state="FETCHED")
        if candidate is None:
            raise DdeError(
                "PROVIDER_ERROR",
                "registry item payload cannot be normalized",
                retryable=False,
                details={"provider": self.provider_key, "item": provider_artifact_key},
            )
        digest = hashlib.sha256(raw).hexdigest()
        candidate = replace(candidate, content_hash=digest, source_uri=url)
        return FetchedSource(candidate=candidate, content=raw)

    async def _index(self) -> RegistryIndex:
        now = self._clock()
        cached = self._cache.get(self.provider_key)
        if cached is not None and now - cached[0] < self._cache_ttl_seconds:
            return cached[1]
        async with self._index_lock:
            now = self._clock()
            cached = self._cache.get(self.provider_key)
            if cached is not None and now - cached[0] < self._cache_ttl_seconds:
                return cached[1]
            raw = await self._fetcher(self.spec.index_url, INDEX_MAX_BYTES)
            payload = _json_value(
                raw, provider=self.provider_key, role="registry index"
            )
            index = _parse_index(payload, provider=self.provider_key)
            self._cache[self.provider_key] = (now, index)
            return index

    @staticmethod
    def _find(index: RegistryIndex, name: str) -> Mapping[str, object] | None:
        return next((item for item in index.items if item.get("name") == name), None)

    def _candidate(
        self,
        item: Mapping[str, object],
        *,
        index: RegistryIndex,
        retrieval_state: str,
    ) -> SourceCandidate | None:
        name = item.get("name")
        if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
            return None
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            title = name.replace("-", " ").replace("_", " ").title()
        registry_type = str(item.get("type") or "registry:ui")
        deps = _string_values(item.get("dependencies"))
        registry_deps = _string_values(item.get("registryDependencies"))
        dev_deps = _string_values(item.get("devDependencies"))
        dependency_manifest = tuple(dict.fromkeys((*deps, *registry_deps, *dev_deps)))
        description = item.get("description")
        return SourceCandidate(
            provider_artifact_key=name,
            artifact_kind=_artifact_kind(registry_type),
            title=title.strip(),
            source_uri=self.spec.item_url(name),
            framework=self.spec.framework,
            supported_archetypes=(),
            dependency_manifest=dependency_manifest,
            license_state=self.spec.license_state,
            license_ids=self.spec.license_ids,
            security_state="UNKNOWN",
            accessibility_state="UNKNOWN",
            compatibility_state="UNKNOWN",
            retrieval_state=retrieval_state,
            metadata={
                "registry_type": registry_type,
                "registry_name": index.registry_name,
                "registry_homepage": index.homepage,
                "registry_index_url": self.spec.index_url,
                "description": description if isinstance(description, str) else None,
                "license_evidence_uri": self.spec.license_evidence_uri,
                "public_registry_transport": "dde.shadcn-registry-http/1",
            },
        )

    async def _fetch(self, url: str, max_bytes: int) -> bytes:
        return await asyncio.to_thread(self._fetch_sync, url, max_bytes)

    def _fetch_sync(self, url: str, max_bytes: int) -> bytes:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in self.spec.allowed_hosts:
            raise DdeError(
                "POLICY_DENIED",
                "registry request escaped its configured HTTPS host allowlist",
                retryable=False,
                details={"provider": self.provider_key, "host": parsed.hostname},
            )
        request = urllib.request.Request(  # noqa: S310
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "DDE-Source-Intelligence/1",
            },
        )
        try:
            with urllib.request.urlopen(  # noqa: S310
                request, timeout=DEFAULT_TIMEOUT_SECONDS
            ) as response:
                final = urllib.parse.urlparse(response.geturl())
                if (
                    final.scheme != "https"
                    or final.hostname not in self.spec.allowed_hosts
                ):
                    raise DdeError(
                        "POLICY_DENIED",
                        "registry redirect escaped its configured HTTPS host allowlist",
                        retryable=False,
                        details={"provider": self.provider_key, "host": final.hostname},
                    )
                content_type = str(response.headers.get("Content-Type") or "").lower()
                if "json" not in content_type:
                    raise DdeError(
                        "PROVIDER_ERROR",
                        "registry endpoint did not return JSON",
                        retryable=False,
                        details={
                            "provider": self.provider_key,
                            "content_type": content_type,
                        },
                    )
                declared = response.headers.get("Content-Length")
                if declared and declared.isdigit() and int(declared) > max_bytes:
                    raise DdeError(
                        "POLICY_DENIED",
                        "registry response exceeds the DDE fetch bound",
                        retryable=False,
                        details={
                            "provider": self.provider_key,
                            "maximum_bytes": max_bytes,
                        },
                    )
                body = response.read(max_bytes + 1)
        except DdeError:
            raise
        except urllib.error.HTTPError as exc:
            code = (
                "PROVIDER_AUTH_REQUIRED"
                if exc.code in {401, 403}
                else "PROVIDER_UNAVAILABLE"
            )
            raise DdeError(
                code,
                f"registry HTTP request failed with status {exc.code}",
                retryable=exc.code >= 500,
                details={"provider": self.provider_key, "status": exc.code},
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise DdeError(
                "PROVIDER_UNAVAILABLE",
                "registry network request failed",
                retryable=True,
                details={"provider": self.provider_key, "reason": type(exc).__name__},
            ) from exc
        if len(body) > max_bytes:
            raise DdeError(
                "POLICY_DENIED",
                "registry response exceeds the DDE fetch bound",
                retryable=False,
                details={"provider": self.provider_key, "maximum_bytes": max_bytes},
            )
        return bytes(body)


def _json_value(raw: bytes, *, provider: str, role: str) -> object:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DdeError(
            "PROVIDER_ERROR",
            f"{role} is not valid UTF-8 JSON",
            retryable=False,
            details={"provider": provider},
        ) from exc


def _json_object(raw: bytes, *, provider: str, role: str) -> Mapping[str, object]:
    payload = _json_value(raw, provider=provider, role=role)
    if not isinstance(payload, Mapping):
        raise DdeError(
            "PROVIDER_ERROR",
            f"{role} is not a JSON object",
            retryable=False,
            details={"provider": provider},
        )
    return payload


def _parse_index(payload: object, *, provider: str) -> RegistryIndex:
    name: str | None = None
    homepage: str | None = None
    raw_items: object = payload
    if isinstance(payload, Mapping):
        raw_name = payload.get("name")
        raw_homepage = payload.get("homepage")
        name = raw_name if isinstance(raw_name, str) and raw_name else None
        homepage = (
            raw_homepage if isinstance(raw_homepage, str) and raw_homepage else None
        )
        raw_items = payload.get("items")
    if not isinstance(raw_items, Sequence) or isinstance(
        raw_items, (str, bytes, bytearray)
    ):
        raise DdeError(
            "PROVIDER_ERROR",
            "registry index contains no items array",
            retryable=False,
            details={"provider": provider},
        )
    items = tuple(item for item in raw_items if isinstance(item, Mapping))
    if not items:
        raise DdeError(
            "PROVIDER_ERROR",
            "registry index contains no normalizable items",
            retryable=False,
            details={"provider": provider},
        )
    return RegistryIndex(registry_name=name, homepage=homepage, items=items)


def _string_values(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def _artifact_kind(registry_type: str) -> str:
    return {
        "registry:block": "TEMPLATE",
        "registry:style": "THEME",
        "registry:theme": "THEME",
        "registry:font": "FOUNDATION",
        "registry:base": "FOUNDATION",
    }.get(registry_type, "COMPONENT")


SHADCN_SPEC = RegistrySpec(
    provider_key="shadcn",
    display_name="shadcn/ui",
    index_url="https://ui.shadcn.com/r/index.json",
    item_url_template="https://ui.shadcn.com/r/styles/new-york-v4/{name}.json",
    license_state="OPEN_REUSE",
    license_ids=("MIT",),
    license_evidence_uri="https://github.com/shadcn-ui/ui/blob/main/LICENSE.md",
)

REUI_SPEC = RegistrySpec(
    provider_key="reui",
    display_name="ReUI",
    index_url="https://reui.io/r/registry.json",
    item_url_template="https://reui.io/r/{name}.json",
    license_state="OPEN_REUSE",
    license_ids=("MIT",),
    license_evidence_uri="https://github.com/keenthemes/reui/blob/main/LICENSE.md",
)

MAGIC_UI_SPEC = RegistrySpec(
    provider_key="magic-ui",
    display_name="Magic UI",
    index_url="https://magicui.design/registry.json",
    item_url_template="https://magicui.design/r/{name}.json",
    license_state="OPEN_REUSE",
    license_ids=("MIT",),
    license_evidence_uri="https://github.com/magicuidesign/magicui/blob/main/LICENSE.md",
)

ACETERNITY_SPEC = RegistrySpec(
    provider_key="aceternity",
    display_name="Aceternity UI",
    index_url="https://ui.aceternity.com/registry.json",
    item_url_template="https://ui.aceternity.com/registry/{name}.json",
    # Public registry availability does not prove reuse terms. Until DDE has
    # pinned license evidence for this provider, it remains discoverable and
    # fetchable but admission fails closed on UNKNOWN licensing.
    license_state="UNKNOWN",
)

DEFAULT_PUBLIC_REGISTRY_SPECS: Final[tuple[RegistrySpec, ...]] = (
    SHADCN_SPEC,
    REUI_SPEC,
    MAGIC_UI_SPEC,
    ACETERNITY_SPEC,
)
