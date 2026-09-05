"""Provider-neutral M8 DesignSourceAdapter contracts and first-party adapters."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.donor_artifact import DonorArtifact
from engine.donor.repository import DonorRepository
from engine.studio.pxg.service import PxgService
from engine.truth.db import open_unit_of_work


@dataclass(frozen=True)
class SourceQueryContext:
    tenant_id: UUID
    project_id: UUID


@dataclass(frozen=True)
class SourceHealth:
    status: str
    capabilities: tuple[str, ...]
    detail: str | None = None
    item_count: int | None = None


@dataclass(frozen=True)
class SourceCandidate:
    provider_artifact_key: str
    artifact_kind: str
    title: str
    source_uri: str | None = None
    version_ref: str | None = None
    content_hash: str | None = None
    framework: str | None = None
    supported_archetypes: tuple[str, ...] = ()
    dependency_manifest: tuple[str, ...] = ()
    license_state: str = "UNKNOWN"
    license_ids: tuple[str, ...] = ()
    security_state: str = "UNKNOWN"
    accessibility_state: str = "UNKNOWN"
    compatibility_state: str = "UNKNOWN"
    retrieval_state: str = "INDEXED"
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class FetchedSource:
    candidate: SourceCandidate
    content: bytes | None


class DesignSourceAdapter(Protocol):
    provider_key: str

    async def health(self, context: SourceQueryContext) -> SourceHealth: ...
    async def search(
        self, context: SourceQueryContext, query: str
    ) -> tuple[SourceCandidate, ...]: ...
    async def inspect(
        self, context: SourceQueryContext, provider_artifact_key: str
    ) -> SourceCandidate | None: ...
    async def fetch(
        self, context: SourceQueryContext, provider_artifact_key: str
    ) -> FetchedSource | None: ...


class ProjectNativeSourceAdapter:
    provider_key = "project-native"

    def __init__(self, engine: AsyncEngine, *, pxg: PxgService | None = None) -> None:
        self._pxg = pxg or PxgService(engine)

    async def health(self, context: SourceQueryContext) -> SourceHealth:
        graph = await self._pxg.load(
            tenant_id=context.tenant_id, project_id=context.project_id
        )
        count = len(graph.nodes_of_kind("component"))
        return SourceHealth(
            "AVAILABLE",
            ("search", "inspect", "reuse", "provenance"),
            f"PXG revision {graph.revision}; {count} component(s)",
            count,
        )

    async def search(
        self, context: SourceQueryContext, query: str
    ) -> tuple[SourceCandidate, ...]:
        graph = await self._pxg.load(
            tenant_id=context.tenant_id, project_id=context.project_id
        )
        needle = query.strip().lower()
        rows: list[SourceCandidate] = []
        for node in graph.nodes_of_kind("component"):
            haystack = f"{node.title} {node.pxg_key}".lower()
            if needle and needle not in haystack:
                continue
            framework = node.attributes.get("framework")
            rows.append(
                SourceCandidate(
                    provider_artifact_key=node.pxg_key,
                    artifact_kind="COMPONENT",
                    title=node.title,
                    source_uri=(node.source_refs[0].path if node.source_refs else None),
                    framework=str(framework) if framework else None,
                    license_state="OPEN_REUSE",
                    security_state="UNKNOWN",
                    accessibility_state="UNKNOWN",
                    compatibility_state="PASS",
                    retrieval_state="INSPECTED",
                    metadata={
                        "pxg_key": node.pxg_key,
                        "source_refs": [
                            item.model_dump(mode="json") for item in node.source_refs
                        ],
                        "provenance": dict(node.provenance),
                    },
                )
            )
        return tuple(rows)

    async def inspect(
        self, context: SourceQueryContext, provider_artifact_key: str
    ) -> SourceCandidate | None:
        rows = await self.search(context, "")
        return next(
            (row for row in rows if row.provider_artifact_key == provider_artifact_key),
            None,
        )

    async def fetch(
        self, context: SourceQueryContext, provider_artifact_key: str
    ) -> FetchedSource | None:
        candidate = await self.inspect(context, provider_artifact_key)
        return FetchedSource(candidate, None) if candidate else None


class DdeLibrarySourceAdapter:
    """Versioned DDE-approved component catalog.

    An empty catalog is a real empty state, never a reason to invent entries.
    """

    provider_key = "dde-library"

    def __init__(self, catalog_path: Path | None = None) -> None:
        self._catalog_path = catalog_path or (
            Path(__file__).resolve().parents[3]
            / "schemas"
            / "design"
            / "dde_component_library.json"
        )

    def _rows(self) -> tuple[dict[str, object], ...]:
        if not self._catalog_path.is_file():
            return ()
        raw = json.loads(self._catalog_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not isinstance(raw.get("components"), list):
            return ()
        return tuple(row for row in raw["components"] if isinstance(row, dict))

    async def health(self, context: SourceQueryContext) -> SourceHealth:
        del context
        if not self._catalog_path.is_file():
            return SourceHealth(
                "NOT_CONFIGURED",
                ("search", "inspect", "fetch", "provenance"),
                "versioned DDE component catalog is absent",
            )
        rows = self._rows()
        return SourceHealth(
            "AVAILABLE",
            ("search", "inspect", "fetch", "provenance"),
            f"{len(rows)} approved DDE component(s)",
            len(rows),
        )

    @staticmethod
    def _candidate(row: dict[str, object]) -> SourceCandidate | None:
        key = row.get("key")
        title = row.get("title")
        if (
            not isinstance(key, str)
            or not key
            or not isinstance(title, str)
            or not title
        ):
            return None
        source_path = row.get("source_path")
        framework = row.get("framework")
        dependencies = row.get("dependencies")
        archetypes = row.get("supported_archetypes")
        licence = row.get("license_id")
        artifact_kind_raw = str(row.get("artifact_kind") or "COMPONENT").upper()
        artifact_kind = (
            artifact_kind_raw
            if artifact_kind_raw
            in {
                "COMPONENT",
                "TEMPLATE",
                "THEME",
                "FOUNDATION",
                "DIRECTIVE",
                "REFERENCE",
            }
            else "COMPONENT"
        )
        return SourceCandidate(
            provider_artifact_key=key,
            artifact_kind=artifact_kind,
            title=title,
            source_uri=(str(source_path) if isinstance(source_path, str) else None),
            version_ref=(str(row.get("version")) if row.get("version") else None),
            content_hash=(
                str(row.get("content_hash")) if row.get("content_hash") else None
            ),
            framework=str(framework) if isinstance(framework, str) else None,
            supported_archetypes=tuple(str(x) for x in archetypes)
            if isinstance(archetypes, list)
            else (),
            dependency_manifest=tuple(str(x) for x in dependencies)
            if isinstance(dependencies, list)
            else (),
            license_state=(
                str(row.get("license_state"))
                if row.get("license_state")
                in {
                    "OPEN_REUSE",
                    "CONDITIONAL_REUSE",
                    "REFERENCE_ONLY",
                    "REJECTED",
                    "UNKNOWN",
                }
                else (
                    "OPEN_REUSE" if isinstance(licence, str) and licence else "UNKNOWN"
                )
            ),
            license_ids=(str(licence),) if isinstance(licence, str) and licence else (),
            security_state=str(row.get("security_state") or "UNKNOWN"),
            accessibility_state=str(row.get("accessibility_state") or "UNKNOWN"),
            compatibility_state=str(row.get("compatibility_state") or "UNKNOWN"),
            retrieval_state="INSPECTED",
            metadata={
                "catalog": "schemas/design/dde_component_library.json",
                "token_mapping_report": row.get("token_mapping_report", {}),
                "evidence_refs": row.get("evidence_refs", []),
            },
        )

    async def search(
        self, context: SourceQueryContext, query: str
    ) -> tuple[SourceCandidate, ...]:
        del context
        needle = query.strip().lower()
        result: list[SourceCandidate] = []
        for row in self._rows():
            candidate = self._candidate(row)
            if candidate is None:
                continue
            if (
                needle
                and needle
                not in f"{candidate.title} {candidate.provider_artifact_key}".lower()
            ):
                continue
            result.append(candidate)
        return tuple(result)

    async def inspect(
        self, context: SourceQueryContext, provider_artifact_key: str
    ) -> SourceCandidate | None:
        del context
        return next(
            (
                candidate
                for row in self._rows()
                if (candidate := self._candidate(row)) is not None
                and candidate.provider_artifact_key == provider_artifact_key
            ),
            None,
        )

    @staticmethod
    def _read_catalog_content(source_uri: str) -> bytes | None:
        root = Path(__file__).resolve().parents[3]
        target = (root / source_uri).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            return None
        return target.read_bytes() if target.is_file() else None

    async def fetch(
        self, context: SourceQueryContext, provider_artifact_key: str
    ) -> FetchedSource | None:
        candidate = await self.inspect(context, provider_artifact_key)
        if candidate is None:
            return None
        source_uri = candidate.source_uri
        if not source_uri:
            return FetchedSource(candidate, None)
        return FetchedSource(candidate, self._read_catalog_content(source_uri))


class DonorSourceAdapter:
    provider_key = "donors"

    def __init__(
        self, engine: AsyncEngine, *, repository: DonorRepository | None = None
    ) -> None:
        self._engine = engine
        self._repository = repository or DonorRepository()

    async def health(self, context: SourceQueryContext) -> SourceHealth:
        rows = await self._rows(context)
        return SourceHealth(
            "AVAILABLE",
            ("search", "inspect", "reference", "provenance"),
            f"{len(rows)} ingested donor artifact(s)",
            len(rows),
        )

    async def _rows(self, context: SourceQueryContext) -> list[DonorArtifact]:
        async with open_unit_of_work(
            self._engine,
            tenant_id=context.tenant_id,
            project_id=context.project_id,
        ) as uow:
            return await self._repository.list_artifacts_for_project(
                uow.connection, project_id=context.project_id
            )

    @staticmethod
    def _candidate(row: DonorArtifact) -> SourceCandidate:
        source_class = str(row.source_class)
        license_state = {
            "OPEN_REUSE": "OPEN_REUSE",
            "CONDITIONAL_REUSE": "CONDITIONAL_REUSE",
            "SOURCE_REFERENCE_ONLY": "REFERENCE_ONLY",
            "RESTRICTED": "REJECTED",
            "REJECTED": "REJECTED",
            "UNKNOWN": "UNKNOWN",
        }.get(source_class, "UNKNOWN")
        provenance = dict(row.provenance)
        licence = provenance.get("licence_class")
        findings = list(row.injection_findings)
        artifact_kind = (
            "DIRECTIVE"
            if license_state == "REFERENCE_ONLY"
            else ("COMPONENT" if row.media_kind == "source_tree" else "REFERENCE")
        )
        return SourceCandidate(
            provider_artifact_key=str(row.donor_artifact_id),
            artifact_kind=artifact_kind,
            title=str(row.source_uri),
            source_uri=str(row.source_uri),
            content_hash=str(row.content_hash),
            license_state=license_state,
            license_ids=(str(licence),) if licence and licence != "UNKNOWN" else (),
            security_state="FAIL" if findings else "PASS",
            accessibility_state="UNKNOWN",
            compatibility_state="UNKNOWN",
            retrieval_state="FETCHED",
            metadata={
                "donor_artifact_id": str(row.donor_artifact_id),
                "source_class": source_class,
                "injection_findings": findings,
                "donor_provenance": provenance,
            },
        )

    async def search(
        self, context: SourceQueryContext, query: str
    ) -> tuple[SourceCandidate, ...]:
        needle = query.strip().lower()
        rows = await self._rows(context)
        result = [
            self._candidate(row)
            for row in rows
            if not needle or needle in str(row.source_uri).lower()
        ]
        return tuple(result)

    async def inspect(
        self, context: SourceQueryContext, provider_artifact_key: str
    ) -> SourceCandidate | None:
        return next(
            (
                row
                for row in await self.search(context, "")
                if row.provider_artifact_key == provider_artifact_key
            ),
            None,
        )

    async def fetch(
        self, context: SourceQueryContext, provider_artifact_key: str
    ) -> FetchedSource | None:
        candidate = await self.inspect(context, provider_artifact_key)
        return FetchedSource(candidate, None) if candidate else None


class TwentyFirstTransport(Protocol):
    async def health(self, context: SourceQueryContext) -> SourceHealth: ...
    async def search(
        self, context: SourceQueryContext, query: str
    ) -> tuple[SourceCandidate, ...]: ...
    async def inspect(
        self, context: SourceQueryContext, artifact_key: str
    ) -> SourceCandidate | None: ...
    async def fetch(
        self, context: SourceQueryContext, artifact_key: str
    ) -> FetchedSource | None: ...


class TwentyFirstSourceAdapter:
    """21st boundary. No direct network fallback exists without certified transport."""

    provider_key = "21st"

    def __init__(self, transport: TwentyFirstTransport | None = None) -> None:
        self._transport = transport

    async def health(self, context: SourceQueryContext) -> SourceHealth:
        if self._transport is None:
            return SourceHealth(
                "NOT_CONFIGURED",
                ("search", "inspect", "fetch", "license", "health"),
                "21st MCP/provider transport is not configured",
            )
        return await self._transport.health(context)

    async def search(
        self, context: SourceQueryContext, query: str
    ) -> tuple[SourceCandidate, ...]:
        if self._transport is None:
            return ()
        return await self._transport.search(context, query)

    async def inspect(
        self, context: SourceQueryContext, provider_artifact_key: str
    ) -> SourceCandidate | None:
        if self._transport is None:
            return None
        return await self._transport.inspect(context, provider_artifact_key)

    async def fetch(
        self, context: SourceQueryContext, provider_artifact_key: str
    ) -> FetchedSource | None:
        if self._transport is None:
            return None
        return await self._transport.fetch(context, provider_artifact_key)
