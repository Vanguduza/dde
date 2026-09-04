"""Descriptor-driven Inspector projection over a selected candidate node."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from engine.contracts.pxg_node import PxgNode
from engine.studio.tokens_catalog import STYLE_PROPERTIES, allowed_values


@dataclass(frozen=True)
class PropertyDescriptor:
    property_id: str
    label: str
    group: str
    value_kind: str
    current_value: object | None
    allowed_values: tuple[str, ...]
    mutation_operation: str
    lock_compatibility: str
    validation: str
    invalidates: tuple[str, ...]


@dataclass(frozen=True)
class InspectorSnapshot:
    pxg_key: str
    title: str
    node_kind: str
    source_refs: tuple[dict[str, object], ...]
    descriptors: tuple[PropertyDescriptor, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "pxg_key": self.pxg_key,
            "title": self.title,
            "node_kind": self.node_kind,
            "source_refs": list(self.source_refs),
            "descriptors": [asdict(item) for item in self.descriptors],
        }


_GROUPS = {
    "spacing": "layout",
    "radius": "layout",
    "z_index": "layout",
    "color": "style",
    "shadow": "style",
    "type": "style",
    "duration": "behavior",
    "easing": "behavior",
}


def project_inspector(node: PxgNode) -> InspectorSnapshot:
    """Expose only properties the governed mutation planner can write."""
    descriptors = tuple(
        PropertyDescriptor(
            property_id=property_name,
            label=property_name.replace("_", " ").title(),
            group=_GROUPS[property_name],
            value_kind="token",
            current_value=node.attributes.get(property_name),
            allowed_values=tuple(sorted(allowed_values(property_name))),
            mutation_operation="SET_PROPERTY",
            lock_compatibility="STYLE",
            validation="design-token-catalogue",
            invalidates=(
                "candidate_render",
                "visual_verification",
                "screen_audit",
            ),
        )
        for property_name in sorted(STYLE_PROPERTIES)
    )
    return InspectorSnapshot(
        pxg_key=node.pxg_key,
        title=node.title,
        node_kind=node.node_kind,
        source_refs=tuple(ref.model_dump(mode="json") for ref in node.source_refs),
        descriptors=descriptors,
    )
