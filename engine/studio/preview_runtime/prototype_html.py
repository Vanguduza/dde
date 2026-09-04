"""Code-backed preview adapter for DDE's admitted prototype HTML target.

This is deliberately narrow. It renders actual `prototypes/screens/*.html`
from the candidate worktree and replays the candidate's governed mutation log
onto that code. A React/Vite project is not silently treated as HTML; it is
UNAVAILABLE until a certified adapter exists for that target.
"""

from __future__ import annotations

import hashlib
import json
import re
from html import escape
from pathlib import PurePosixPath
from uuid import UUID

from engine.contracts.frontend_mutation import FrontendMutation
from engine.contracts.pxg_node import PxgNode
from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError
from engine.studio.canvas import apply_update, screen_relative_path
from engine.studio.preview_runtime.runtime import MaterializedPreview
from engine.studio.pxg.service import PxgGraph
from engine.studio.tokens_catalog import STYLE_PROPERTIES
from engine.workspaces.service import WorkspaceService

_OPEN_DDE_DIV = re.compile(r'<div\s+([^>]*\bdata-dde-el="([^"]+)"[^>]*)>')
_PXG_ATTR = re.compile(r'\sdata-dde-pxg-key="[^"]*"')
_SUPPORTED_PROPERTIES = STYLE_PROPERTIES | frozenset({"label", "variant"})


class PrototypeHtmlPreviewAdapter:
    adapter_id = "prototype-html-v1"

    def __init__(self, workspaces: WorkspaceService) -> None:
        self._workspaces = workspaces

    def validate(
        self,
        *,
        graph: PxgGraph,
        history: tuple[FrontendMutation, ...],
        screen_key: str,
    ) -> str:
        source_path = _screen_source_path(graph, screen_key)
        for mutation in history:
            if mutation.status != "APPLIED":
                continue
            node = graph.node_by_key(mutation.target_key)
            if node is None:
                raise _unavailable(
                    "an applied mutation targets a node absent from the "
                    "candidate graph",
                    mutation_id=str(mutation.mutation_id),
                    target_key=mutation.target_key,
                )
            node_path = _node_source_path(node)
            if not _belongs_to_screen(graph, mutation.target_key, screen_key):
                continue
            if node_path != source_path:
                raise _unavailable(
                    "a mutation in this screen has no stable mapping to its "
                    "preview source",
                    target_key=mutation.target_key,
                    source_path=node_path,
                    screen_source_path=source_path,
                )
            if mutation.operation not in {"SET_PROPERTY", "RESTYLE"}:
                raise _unavailable(
                    "prototype HTML preview cannot materialize this mutation operation",
                    operation=mutation.operation,
                    target_key=mutation.target_key,
                )
            prop = mutation.payload.get("property")
            value = mutation.payload.get("value")
            if not isinstance(prop, str) or prop not in _SUPPORTED_PROPERTIES:
                raise _unavailable(
                    "prototype HTML preview has no deterministic renderer for "
                    "this property",
                    property=str(prop),
                    target_key=mutation.target_key,
                )
            if not isinstance(value, str):
                raise _unavailable(
                    "prototype HTML preview requires a string mutation value",
                    target_key=mutation.target_key,
                )
            _element_id(node)
        return source_path

    def materialize(
        self,
        *,
        workspace: Workspace,
        graph: PxgGraph,
        history: tuple[FrontendMutation, ...],
        screen_key: str,
        preview_session_id: UUID,
    ) -> MaterializedPreview:
        source_path = self.validate(graph=graph, history=history, screen_key=screen_key)
        try:
            html = self._workspaces.read(workspace, source_path).decode("utf-8")
        except FileNotFoundError as exc:
            raise DdeError(
                "CONTEXT_INCOMPLETE",
                "PXG source mapping points to a screen file that is absent from "
                "the candidate workspace",
                retryable=False,
                details={"screen_key": screen_key, "source_path": source_path},
            ) from exc

        for mutation in sorted(history, key=lambda item: item.sequence):
            if mutation.status != "APPLIED" or not _belongs_to_screen(
                graph, mutation.target_key, screen_key
            ):
                continue
            node = graph.node_by_key(mutation.target_key)
            if node is None:
                raise _unavailable(
                    "candidate graph changed during preview materialization",
                    target_key=mutation.target_key,
                )
            if _node_source_path(node) != source_path:
                continue
            html = apply_update(
                html,
                element_id=_element_id(node),
                property_name=str(mutation.payload["property"]),
                value=str(mutation.payload["value"]),
            )

        # This write is candidate-local. Accepted project source is never touched.
        self._workspaces.write(workspace, source_path, html.encode("utf-8"))
        source_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
        instrumented, keys = _instrument(graph, screen_key, source_path, html)
        document = _inject_runtime(
            instrumented,
            preview_session_id=preview_session_id,
            source_hash=source_hash,
        )
        document_path = f".dde/preview/{preview_session_id}.html"
        self._workspaces.write(workspace, document_path, document.encode("utf-8"))
        screen = graph.node_by_key(screen_key)
        route = None
        if screen is not None:
            raw_route = screen.attributes.get("route")
            route = raw_route if isinstance(raw_route, str) and raw_route else None
        return MaterializedPreview(
            source_path=source_path,
            document_path=document_path,
            content_hash=source_hash,
            route=route,
            instrumented_keys=keys,
        )


def _screen_source_path(graph: PxgGraph, screen_key: str) -> str:
    screen = graph.node_by_key(screen_key)
    if screen is None or screen.node_kind != "screen":
        raise _unavailable(
            "selected preview screen is not a PXG screen", screen_key=screen_key
        )
    path = _node_source_path(screen)
    if path is None:
        raise _unavailable(
            "screen has no source reference; source mapping unavailable",
            screen_key=screen_key,
        )
    pure = PurePosixPath(path)
    if len(pure.parts) != 3 or pure.parts[:2] != ("prototypes", "screens"):
        raise _unavailable(
            "screen source requires a runtime adapter other than prototype HTML",
            screen_key=screen_key,
            source_path=path,
        )
    try:
        canonical = screen_relative_path(pure.name)
    except DdeError as exc:
        raise _unavailable(
            "screen source path is not an admitted prototype HTML path",
            screen_key=screen_key,
            source_path=path,
        ) from exc
    if canonical != path:
        raise _unavailable(
            "screen source path is not canonical",
            screen_key=screen_key,
            source_path=path,
        )
    return path


def _node_source_path(node: PxgNode) -> str | None:
    if not node.source_refs:
        return None
    path = node.source_refs[0].path
    return path if path else None


def _element_id(node: PxgNode) -> str:
    value = node.attributes.get("element_id")
    if not isinstance(value, str) or not value:
        raise _unavailable(
            "PXG node has source code but no stable preview element anchor",
            target_key=node.pxg_key,
        )
    return value


def _belongs_to_screen(graph: PxgGraph, key: str, screen_key: str) -> bool:
    current = graph.node_by_key(key)
    seen: set[str] = set()
    while current is not None and current.pxg_key not in seen:
        if current.pxg_key == screen_key:
            return True
        seen.add(current.pxg_key)
        current = graph.node_by_key(current.parent_key) if current.parent_key else None
    return False


def _instrument(
    graph: PxgGraph, screen_key: str, source_path: str, html: str
) -> tuple[str, tuple[str, ...]]:
    by_element: dict[str, str] = {}
    for node in graph.nodes:
        if not _belongs_to_screen(graph, node.pxg_key, screen_key):
            continue
        if _node_source_path(node) != source_path:
            continue
        value = node.attributes.get("element_id")
        if isinstance(value, str) and value:
            by_element[value] = node.pxg_key

    found: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        attrs = match.group(1)
        element_id = match.group(2)
        key = by_element.get(element_id)
        if key is None:
            return match.group(0)
        found.add(key)
        attrs = _PXG_ATTR.sub("", attrs)
        return f'<div {attrs} data-dde-pxg-key="{escape(key, quote=True)}">'

    rendered = _OPEN_DDE_DIV.sub(replace, html)
    missing = sorted(set(by_element.values()) - found)
    if missing:
        raise _unavailable(
            "PXG source mapping names element anchors absent from the candidate screen",
            missing_pxg_keys=missing,
            source_path=source_path,
        )
    return rendered, tuple(sorted(found))


def _inject_runtime(html: str, *, preview_session_id: UUID, source_hash: str) -> str:
    metadata = json.dumps(
        {"previewSessionId": str(preview_session_id), "contentHash": source_hash},
        separators=(",", ":"),
    )
    lines = [
        '<script id="dde-preview-runtime">',
        "(() => {",
        f"  const meta = {metadata};",
        "  const send = (kind, payload = {}) => parent.postMessage({",
        '    type: "dde.preview", kind, ...meta, ...payload',
        '  }, "*");',
        "  const geometry = (node) => {",
        "    const r = node.getBoundingClientRect();",
        "    return {x:r.x,y:r.y,width:r.width,height:r.height};",
        "  };",
        '  document.addEventListener("pointerdown", (event) => {',
        "    const target = event.target instanceof Element",
        '      ? event.target.closest("[data-dde-pxg-key]") : null;',
        "    if (!target) return;",
        '    send("selection", {',
        '      pxgKey: target.getAttribute("data-dde-pxg-key"),',
        "      geometry: geometry(target)",
        "    });",
        "  }, true);",
        '  addEventListener("DOMContentLoaded", () => send("ready"),',
        "    {once:true});",
        '  addEventListener("error", (event) =>',
        '    send("runtime_error", {detail:String(event.message ||',
        '      "runtime error")}));',
        "})();",
        "</script>",
    ]
    script = "\n".join(lines)
    if "</body>" in html:
        return html.replace("</body>", f"{script}</body>", 1)
    return html + script


def _unavailable(message: str, **details: object) -> DdeError:
    return DdeError("CONTEXT_INCOMPLETE", message, retryable=False, details=details)
