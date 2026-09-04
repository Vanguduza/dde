"""Preview runtime contracts for DDE-069.

A runtime adapter turns an isolated candidate workspace into something the
Frontend Studio can render. It never owns accepted design state and it cannot
mint LIVE by itself: PreviewService only promotes LOADING -> LIVE after the
browser attests the exact candidate source hash and the revisions still match.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from engine.contracts.frontend_mutation import FrontendMutation
from engine.contracts.workspace import Workspace
from engine.studio.pxg.service import PxgGraph


@dataclass(frozen=True)
class MaterializedPreview:
    source_path: str
    document_path: str
    content_hash: str
    route: str | None
    instrumented_keys: tuple[str, ...]


class PreviewRuntimeAdapter(Protocol):
    """Platform-neutral materialization seam.

    The initial admitted adapter is prototype HTML. React/Vite, Expo and other
    runtimes can implement this contract without changing candidate, mutation or
    Inspector authority.
    """

    adapter_id: str

    def validate(
        self,
        *,
        graph: PxgGraph,
        history: tuple[FrontendMutation, ...],
        screen_key: str,
    ) -> str:
        """Return the implementation path or raise a typed unavailable error."""

    def materialize(
        self,
        *,
        workspace: Workspace,
        graph: PxgGraph,
        history: tuple[FrontendMutation, ...],
        screen_key: str,
        preview_session_id: UUID,
    ) -> MaterializedPreview:
        """Write candidate code + sandbox preview document into the workspace."""
