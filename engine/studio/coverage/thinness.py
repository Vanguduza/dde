"""DDE-069 screen thinness detection (FRONTEND_STUDIO_REV3 section 13.5).

A screen can satisfy every structural obligation and still be a shell: a
happy path with no empty state, a table with no loading treatment, a
destructive action with no confirmation. These are deterministic
detections over the Project Experience Graph, not model prose -- each one
names the specific missing node kind, so it is actionable and arguable
rather than an opinion.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from engine.contracts.frontend_coverage_snapshot import Finding
from engine.contracts.pxg_node import PxgNode
from engine.studio.pxg.service import PxgGraph

#: A screen carrying real data is expected to say what it looks like when
#: that data is absent, slow or broken. These are the state names the
#: detector looks for among a screen's `state` children.
EXPECTED_DATA_STATES: Final[tuple[str, ...]] = ("loading", "empty", "error")


def detect(
    graph: PxgGraph, *, screen_keys: Sequence[str] | None = None
) -> tuple[Finding, ...]:
    """Return thinness findings for the named screens, or every screen."""
    screens = [
        node
        for node in graph.nodes_of_kind("screen")
        if screen_keys is None or node.pxg_key in screen_keys
    ]
    findings: list[Finding] = []
    for screen in screens:
        descendants = _descendants(graph, screen.pxg_key)
        state_names = {
            str(node.attributes.get("state_name") or node.title).strip().lower()
            for node in descendants
            if node.node_kind == "state"
        }
        interactions = [node for node in descendants if node.node_kind == "interaction"]
        bindings = [node for node in descendants if node.node_kind == "data_binding"]
        responsive = [
            node for node in descendants if node.node_kind == "responsive_state"
        ]

        if bindings:
            missing = [name for name in EXPECTED_DATA_STATES if name not in state_names]
            if missing:
                findings.append(
                    Finding(
                        finding_kind="THIN_SCREEN",
                        dimension="data_state",
                        pxg_key=screen.pxg_key,
                        obligation_id=None,
                        detail=(
                            "screen binds data but declares no "
                            + "/".join(missing)
                            + " state"
                        ),
                    )
                )

        for interaction in interactions:
            if not interaction.attributes.get("command_ref"):
                findings.append(
                    Finding(
                        finding_kind="THIN_SCREEN",
                        dimension="interaction",
                        pxg_key=interaction.pxg_key,
                        obligation_id=None,
                        detail=(
                            "interaction has no command_ref, so nothing "
                            "actually happens when it is used"
                        ),
                    )
                )
            elif interaction.attributes.get(
                "destructive"
            ) and not interaction.attributes.get("confirmation_ref"):
                findings.append(
                    Finding(
                        finding_kind="THIN_SCREEN",
                        dimension="interaction",
                        pxg_key=interaction.pxg_key,
                        obligation_id=None,
                        detail=(
                            "destructive interaction has no confirmation or "
                            "recovery path"
                        ),
                    )
                )

        if screen.attributes.get("responsive_required") and not responsive:
            findings.append(
                Finding(
                    finding_kind="THIN_SCREEN",
                    dimension="responsive",
                    pxg_key=screen.pxg_key,
                    obligation_id=None,
                    detail="screen requires responsive variants but declares none",
                )
            )

        if not graph.children_of(screen.pxg_key):
            findings.append(
                Finding(
                    finding_kind="THIN_SCREEN",
                    dimension="screen",
                    pxg_key=screen.pxg_key,
                    obligation_id=None,
                    detail="screen node has no regions or components beneath it",
                )
            )
    return tuple(findings)


def _descendants(graph: PxgGraph, root_key: str) -> tuple[PxgNode, ...]:
    """Breadth-first containment walk. Cycles cannot occur through
    parent_key alone, but the seen-set keeps a corrupted graph bounded."""
    seen: set[str] = set()
    frontier = [root_key]
    collected: list[PxgNode] = []
    while frontier:
        current = frontier.pop()
        for child in graph.children_of(current):
            if child.pxg_key in seen:
                continue
            seen.add(child.pxg_key)
            collected.append(child)
            frontier.append(child.pxg_key)
    return tuple(collected)
