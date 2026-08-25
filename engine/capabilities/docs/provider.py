"""In-process documentation provider for capability.docs_provider (DDE-050).

Sources are directories under a docs root, each with a `manifest.json`
naming its slug and pinned version ("version-pinned external docs",
Ch.5.2). No network fetch exists here — sources are materialised on disk
by an operator or a future governed sync (network discovery is DDE-066's
EDR-gated surface). Reads screen for prompt-injection phrases (same
classes as `engine.donor.injection`) because documentation is untrusted
external evidence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from engine.core.errors import DdeError
from engine.donor.injection import screen_donor_text

_DOC_SUFFIXES = frozenset({".md", ".txt", ".rst", ".html"})


@dataclass(frozen=True)
class DocSource:
    """One registered documentation source and its pinned version."""

    slug: str
    version: str


@dataclass(frozen=True)
class DocContent:
    """One document read from a source, with its provenance intact."""

    slug: str
    version: str
    path: str
    text: str
    injection_findings: list[str] = field(default_factory=list)


class DocsProvider(Protocol):
    """T1-brokered documentation access. Callers must hold an active
    `capability.docs_provider` lease before invoking `read` — this
    protocol grants no write authority over any source."""

    async def is_active(self) -> bool: ...

    async def list_sources(self) -> list[DocSource]: ...

    async def read(self, slug: str) -> list[DocContent]: ...


class InProcessDocsProvider:
    """Read-only provider over `<root>/<slug>/manifest.json` sources."""

    MAX_FILE_BYTES = 1_000_000
    MAX_DOCS_PER_SOURCE = 50

    def __init__(self, root: Path) -> None:
        self._root = root

    async def is_active(self) -> bool:
        return self._root.is_dir()

    async def list_sources(self) -> list[DocSource]:
        if not self._root.is_dir():
            return []
        sources: list[DocSource] = []
        for child in sorted(self._root.iterdir()):
            manifest = child / "manifest.json"
            if not child.is_dir() or not manifest.is_file():
                continue
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            slug = data.get("slug")
            version = data.get("version")
            if isinstance(slug, str) and isinstance(version, str):
                sources.append(DocSource(slug=slug, version=version))
        return sources

    async def read(self, slug: str) -> list[DocContent]:
        source_dir = self._require_source(slug)
        contents: list[DocContent] = []
        version = self._version_of(source_dir)
        count = 0
        for path in sorted(source_dir.rglob("*")):
            if count >= self.MAX_DOCS_PER_SOURCE:
                break
            if not path.is_file() or path.suffix.lower() not in _DOC_SUFFIXES:
                continue
            if path.stat().st_size > self.MAX_FILE_BYTES:
                raise DdeError(
                    "POLICY_DENIED",
                    "documentation file exceeds the read ceiling; the "
                    "source must be re-chunked by its maintainer",
                    details={"path": str(path.relative_to(source_dir))},
                )
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            rel = path.relative_to(source_dir).as_posix()
            contents.append(
                DocContent(
                    slug=slug,
                    version=version,
                    path=rel,
                    text=text,
                    injection_findings=screen_donor_text(text),
                )
            )
            count += 1
        return contents

    def _require_source(self, slug: str) -> Path:
        if not self._root.is_dir():
            raise DdeError(
                "POLICY_DENIED",
                "no documentation sources directory is configured",
                details={"root": str(self._root)},
            )
        if (
            not slug
            or slug in (".", "..")
            or "/" in slug
            or "\\" in slug
            or slug.startswith(".")
        ):
            raise DdeError(
                "VALIDATION_FAILED",
                f"documentation slug {slug!r} is not a plain source name",
                details={},
            )
        source_dir = self._root / slug
        if not (source_dir / "manifest.json").is_file():
            raise DdeError(
                "VALIDATION_FAILED",
                f"unknown documentation source {slug!r}",
                details={"root": str(self._root)},
            )
        return source_dir

    @staticmethod
    def _version_of(source_dir: Path) -> str:
        try:
            data = json.loads(
                (source_dir / "manifest.json").read_text(encoding="utf-8")
            )
            version = data.get("version")
            if isinstance(version, str):
                return version
        except (OSError, json.JSONDecodeError):
            pass
        return "unpinned"
