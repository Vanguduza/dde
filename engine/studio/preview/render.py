"""Deterministic materialization of a candidate PXG into executable preview code."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Final
from uuid import UUID

from engine.contracts.pxg_node import PxgNode
from engine.core.errors import DdeError
from engine.studio.pxg.service import PxgGraph
from engine.studio.tokens_pin import load_token_sheet

DOCUMENT_PATH: Final = "dde-preview/index.html"


@dataclass(frozen=True)
class PreviewDocument:
    content: bytes
    content_sha256: str
    route_key: str
    candidate_pxg_revision: int


def render_candidate(
    graph: PxgGraph,
    *,
    candidate_id: UUID,
    preview_session_id: UUID,
    route_key: str,
) -> PreviewDocument:
    """Build the exact candidate graph as an isolated executable document.

    The generated code is the DDE-native renderer implementation of the
    candidate mutation log. It is not a screenshot or unrelated fixture:
    every rendered node comes from the effective candidate PXG and carries
    its stable ``pxg_key`` for selection.
    """
    screen = graph.node_by_key(route_key)
    if screen is None or screen.node_kind != "screen":
        raise DdeError(
            "VALIDATION_FAILED",
            "preview route must identify a candidate screen",
            retryable=False,
            details={"route_key": route_key},
        )

    children: dict[str | None, list[PxgNode]] = {}
    for node in graph.nodes:
        children.setdefault(node.parent_key, []).append(node)
    for values in children.values():
        values.sort(key=lambda item: item.pxg_key)

    body = _node_html(screen, children)
    metadata = json.dumps(
        {
            "candidateId": str(candidate_id),
            "previewSessionId": str(preview_session_id),
            "candidatePxgRevision": graph.revision,
            "routeKey": route_key,
        },
        separators=(",", ":"),
    ).replace("</", "<\\/")
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{html.escape(screen.title)} · DDE candidate preview</title>
  <style>{_preview_css()}</style>
</head>
<body>
  <main data-dde-candidate-id="{candidate_id}" data-dde-preview-revision="{graph.revision}">
    {body}
  </main>
  <script>
    const preview = {metadata};
    document.addEventListener("click", (event) => {{
      const target = event.target instanceof Element
        ? event.target.closest("[data-dde-pxg-key]")
        : null;
      if (!target) return;
      event.preventDefault();
      parent.postMessage({{
        type: "dde.preview.selection",
        previewSessionId: preview.previewSessionId,
        candidateId: preview.candidateId,
        candidatePxgRevision: preview.candidatePxgRevision,
        pxgKey: target.getAttribute("data-dde-pxg-key")
      }}, "*");
    }});
  </script>
</body>
</html>
"""
    content = document.encode("utf-8")
    return PreviewDocument(
        content=content,
        content_sha256=sha256(content).hexdigest(),
        route_key=route_key,
        candidate_pxg_revision=graph.revision,
    )


def _node_html(
    node: PxgNode,
    children: dict[str | None, list[PxgNode]],
) -> str:
    child_markup = "".join(
        _node_html(child, children) for child in children.get(node.pxg_key, [])
    )
    if not child_markup:
        child_markup = '<span class="dde-preview-empty">No child components</span>'

    classes = f"dde-node dde-node-{html.escape(node.node_kind)}"
    style = _node_style(node)
    return (
        f'<section class="{classes}" data-dde-pxg-key="{html.escape(node.pxg_key)}" '
        f'data-dde-node-kind="{html.escape(node.node_kind)}" style="{style}" '
        'tabindex="0">'
        f'<span class="dde-node-label">{html.escape(node.title)}</span>'
        f'<div class="dde-node-children">{child_markup}</div>'
        "</section>"
    )


def _node_style(node: PxgNode) -> str:
    declarations: list[str] = []
    spacing = node.attributes.get("spacing")
    if isinstance(spacing, str):
        declarations.append(f"--candidate-spacing:{_spacing_px(spacing)}px")
    color = node.attributes.get("color")
    if isinstance(color, str):
        declarations.append(f"--candidate-color:{_resolved_color(color)}")
    return ";".join(declarations)


def _spacing_px(token: str) -> int:
    properties = load_token_sheet().raw["properties"]["spacing"]["properties"]
    entry = properties.get(token)
    if not isinstance(entry, dict) or not isinstance(entry.get("const"), int):
        raise DdeError(
            "POLICY_DENIED",
            "candidate contains an unknown spacing token",
            retryable=False,
            details={"token": token},
        )
    return int(entry["const"])


def _resolved_color(alias: str) -> str:
    sheet = load_token_sheet().raw
    semantic = sheet["properties"]["color"]["properties"]["semantic"]["properties"]
    entry = next(
        (
            value
            for name, value in semantic.items()
            if _css_alias(name) == alias and isinstance(value, dict)
        ),
        None,
    )
    if not isinstance(entry, dict):
        raise DdeError(
            "POLICY_DENIED",
            "candidate contains an unknown semantic color token",
            retryable=False,
            details={"token": alias},
        )
    palette_alias = entry["const"]
    palette = sheet["properties"]["color"]["properties"]["palette"]["properties"]
    palette_name = _palette_name(str(palette_alias))
    value = palette.get(palette_name, {}).get("const")
    if not isinstance(value, str):
        raise DdeError(
            "POLICY_DENIED",
            "semantic color token does not resolve to the token sheet",
            retryable=False,
            details={"token": alias},
        )
    return value


def _css_alias(name: str) -> str:
    chars: list[str] = []
    for index, char in enumerate(name):
        if char.isupper() and index:
            chars.append("-")
        chars.append(char.lower())
    return "--" + "".join(chars)


def _palette_name(alias: str) -> str:
    target = alias.removeprefix("--")
    return "".join(
        part if index == 0 else part.capitalize()
        for index, part in enumerate(target.split("-"))
    )


def _preview_css() -> str:
    return """
:root{color-scheme:light;font-family:Inter,ui-sans-serif,system-ui,sans-serif}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;background:#f7f8fb;color:#111827}
main{min-height:100vh;padding:24px}
.dde-node{--candidate-spacing:16px;--candidate-color:#111827;display:flex;
flex-direction:column;gap:var(--candidate-spacing);padding:var(--candidate-spacing);
border:1px solid #d2d7e5;border-radius:8px;background:#fff;color:var(--candidate-color)}
.dde-node+.dde-node{margin-top:12px}
.dde-node:focus{outline:2px solid #4f46e5;outline-offset:2px}
.dde-node-label{font-size:12px;font-weight:600;letter-spacing:.01em}
.dde-node-children{display:flex;flex-direction:column;gap:var(--candidate-spacing)}
.dde-node-screen{min-height:calc(100vh - 48px)}
.dde-node-region{background:#f3f5f9}
.dde-node-component{border-style:dashed}
.dde-preview-empty{font-size:12px;color:#5d6473}
""".strip()
