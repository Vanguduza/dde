"""DDE-069 design manifest -- the machine-readable provider return contract.

A design provider's *prose* is not a contract. If DDE parsed a final
assistant message for "here are three directions", `/design` would work
until the day a model phrased itself differently, and the failure would
look like DDE's. So the certified Claude Design transport declares this
manifest as the only thing it will accept back, hands its JSON Schema to
the harness for structured-output validation, and re-validates the result
here rather than trusting that validation happened.

Two checks in `parse_manifest` are boundary checks, not formatting checks:

*Ingress scope.* A direction may only name PXG keys that
`DesignEditContext` actually exported. `context.py` bounds what leaves
DDE; this bounds what may come back and claim to be about the project. A
provider that returns a direction for an unexported node is refused, not
quarantined -- the artifact is not merely low quality, it is about
something the provider was never shown.

*Deliverable backing.* Every direction names a `preview_path` the
transport must be able to tie to an observed, successful write into the
provider project. A direction with no backing file is a claim with no
artifact behind it, which is exactly the "artboard labelled LIVE" failure
FRONTEND_STUDIO_REV3 forbids.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from engine.core.errors import DdeError

#: Bumped when the contract changes shape. Recorded in artifact provenance
#: so an artifact generated under an older contract stays identifiable.
MANIFEST_VERSION: Final = "dde.design.manifest/1"

#: Where the transport requires the manifest itself to be written inside
#: the provider project. Persisting it there (not only returning it) means
#: the provider-side record and DDE's record are the same document.
MANIFEST_PATH: Final = "dde-manifest.json"

#: Neutral, matching `gateway.DIRECTION_LABELS`. A provider does not get to
#: invent a label that implies rank.
ALLOWED_LABELS: Final[tuple[str, ...]] = ("A", "B", "C", "D", "E", "F")

MAX_DIRECTION_NODES: Final = 200


#: Handed to the harness as `--json-schema`. Deliberately strict at the top
#: level and permissive inside `tokens`, whose keys are design-system
#: property names this schema must not have to enumerate: the token
#: catalogue, not this file, decides which properties exist.
MANIFEST_JSON_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "manifest_version",
        "provider_project_id",
        "design_system_hash",
        "context_hash",
        "directions",
    ],
    "properties": {
        "manifest_version": {"type": "string", "const": MANIFEST_VERSION},
        "provider_project_id": {"type": "string", "minLength": 1},
        "provider_project_url": {"type": "string"},
        "design_system_hash": {"type": "string", "minLength": 1},
        "context_hash": {"type": "string", "minLength": 1},
        "directions": {
            "type": "array",
            "minItems": 1,
            "maxItems": len(ALLOWED_LABELS),
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["label", "summary", "rationale", "preview_path", "nodes"],
                "properties": {
                    "label": {"type": "string", "enum": list(ALLOWED_LABELS)},
                    "summary": {"type": "string", "minLength": 1},
                    "rationale": {"type": "string", "minLength": 1},
                    "preview_path": {"type": "string", "minLength": 1},
                    "nodes": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["pxg_key", "intent", "tokens"],
                            "properties": {
                                "pxg_key": {"type": "string", "minLength": 1},
                                "intent": {"type": "string", "minLength": 1},
                                "tokens": {
                                    "type": "object",
                                    "additionalProperties": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}


@dataclass(frozen=True)
class DesignDirectionNode:
    pxg_key: str
    intent: str
    tokens: dict[str, str]

    def as_content(self) -> dict[str, object]:
        return {
            "pxg_key": self.pxg_key,
            "intent": self.intent,
            "tokens": dict(self.tokens),
        }


@dataclass(frozen=True)
class DesignDirection:
    label: str
    summary: str
    rationale: str
    preview_path: str
    nodes: tuple[DesignDirectionNode, ...]

    def as_content(self) -> dict[str, object]:
        """The `DesignArtifact.content` body for this direction.

        Deliberately carries no score. There is no evidence for one, and
        `FRONTEND_STUDIO_REV3` 17.2 forbids inventing it.
        """
        return {
            "manifest_version": MANIFEST_VERSION,
            "label": self.label,
            "summary": self.summary,
            "rationale": self.rationale,
            "preview_path": self.preview_path,
            "nodes": [item.as_content() for item in self.nodes],
        }


@dataclass(frozen=True)
class DesignManifest:
    provider_project_id: str
    provider_project_url: str | None
    design_system_hash: str
    context_hash: str
    directions: tuple[DesignDirection, ...]

    @property
    def written_paths(self) -> frozenset[str]:
        """Every path the provider must be observed to have written."""
        return frozenset({MANIFEST_PATH} | {d.preview_path for d in self.directions})


def _violation(message: str, **details: object) -> DdeError:
    """A provider that breaks its own return contract is a provider error.

    `PROVIDER_ERROR` rather than `VALIDATION_FAILED`: nothing the caller
    supplied was malformed, and the operator's next action is to look at
    the provider, not at their own request.
    """
    return DdeError(
        "PROVIDER_ERROR",
        message,
        retryable=False,
        details={"manifest_version": MANIFEST_VERSION, **details},
    )


def parse_manifest(
    payload: object,
    *,
    exported_keys: Iterable[str],
    materializable_keys: Iterable[str],
    design_system_hash: str,
    context_hash: str,
    direction_count: int,
    design_tokens: Mapping[str, Sequence[str]],
) -> DesignManifest:
    """Validate a provider manifest, or refuse it.

    The hashes are echoed by the provider and checked here rather than
    ignored: a manifest generated against a different design-system
    snapshot or a different exported context is not a late artifact, it is
    an artifact about a different project state.
    """
    if not isinstance(payload, Mapping):
        raise _violation("provider returned no manifest object")
    if payload.get("manifest_version") != MANIFEST_VERSION:
        raise _violation(
            "provider returned an unrecognised manifest version",
            returned=str(payload.get("manifest_version")),
        )
    project_id = _text(payload, "provider_project_id")
    if payload.get("design_system_hash") != design_system_hash:
        raise _violation(
            "manifest was generated against a different design-system snapshot",
            expected=design_system_hash,
            returned=str(payload.get("design_system_hash")),
        )
    if payload.get("context_hash") != context_hash:
        raise _violation(
            "manifest was generated against a different exported context",
            expected=context_hash,
            returned=str(payload.get("context_hash")),
        )

    raw_directions = payload.get("directions")
    if not isinstance(raw_directions, Sequence) or isinstance(raw_directions, str):
        raise _violation("manifest carries no directions array")
    if len(raw_directions) != direction_count:
        raise _violation(
            "provider returned a different number of directions than requested",
            requested=direction_count,
            returned=len(raw_directions),
        )

    exported = frozenset(exported_keys)
    materializable = frozenset(materializable_keys)
    if not materializable.issubset(exported):
        raise _violation(
            "transport supplied materializable keys outside exported context"
        )
    seen_labels: set[str] = set()
    seen_paths: set[str] = set()
    directions: list[DesignDirection] = []
    for entry in raw_directions:
        directions.append(
            _direction(
                entry,
                allowed=materializable,
                exported=exported,
                seen_labels=seen_labels,
                seen_paths=seen_paths,
                design_tokens=design_tokens,
            )
        )

    url = payload.get("provider_project_url")
    return DesignManifest(
        provider_project_id=project_id,
        provider_project_url=url if isinstance(url, str) and url else None,
        design_system_hash=design_system_hash,
        context_hash=context_hash,
        directions=tuple(directions),
    )


def _direction(
    entry: object,
    *,
    allowed: frozenset[str],
    exported: frozenset[str],
    seen_labels: set[str],
    seen_paths: set[str],
    design_tokens: Mapping[str, Sequence[str]],
) -> DesignDirection:
    if not isinstance(entry, Mapping):
        raise _violation("a direction is not an object")
    label = _text(entry, "label")
    if label not in ALLOWED_LABELS:
        raise _violation("a direction carries a non-neutral label", label=label)
    if label in seen_labels:
        raise _violation("two directions share one label", label=label)
    seen_labels.add(label)

    preview_path = _text(entry, "preview_path")
    if preview_path.startswith("/") or ".." in preview_path.split("/"):
        raise _violation(
            "a direction names a preview path outside the provider project",
            preview_path=preview_path,
        )
    if preview_path == MANIFEST_PATH:
        raise _violation(
            "a direction claims the manifest itself as its deliverable",
            preview_path=preview_path,
        )
    if preview_path in seen_paths:
        raise _violation(
            "two directions claim the same deliverable", preview_path=preview_path
        )
    seen_paths.add(preview_path)

    raw_nodes = entry.get("nodes")
    if not isinstance(raw_nodes, Sequence) or isinstance(raw_nodes, str):
        raise _violation("a direction carries no nodes array", label=label)
    if not raw_nodes:
        raise _violation("a direction proposes nothing", label=label)
    if len(raw_nodes) > MAX_DIRECTION_NODES:
        raise _violation(
            "a direction exceeds the node bound",
            label=label,
            node_count=len(raw_nodes),
            maximum=MAX_DIRECTION_NODES,
        )

    nodes: list[DesignDirectionNode] = []
    seen_node_keys: set[str] = set()
    for raw in raw_nodes:
        if not isinstance(raw, Mapping):
            raise _violation("a direction node is not an object", label=label)
        pxg_key = _text(raw, "pxg_key")
        if pxg_key not in exported:
            raise _violation(
                "a direction names a node that was never exported to the provider",
                label=label,
                pxg_key=pxg_key,
            )
        if pxg_key not in allowed:
            raise _violation(
                "a direction proposes token edits for a node DDE cannot deterministically materialize",  # noqa: E501
                label=label,
                pxg_key=pxg_key,
            )
        if pxg_key in seen_node_keys:
            raise _violation(
                "a direction names the same PXG node more than once; the proposal is ambiguous",  # noqa: E501
                label=label,
                pxg_key=pxg_key,
            )
        seen_node_keys.add(pxg_key)
        raw_tokens = raw.get("tokens")
        if not isinstance(raw_tokens, Mapping):
            raise _violation("a direction node carries no token map", label=label)
        tokens: dict[str, str] = {}
        for key, value in raw_tokens.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise _violation(
                    "a direction node carries a non-string token entry",
                    label=label,
                    pxg_key=pxg_key,
                )
            allowed_values = design_tokens.get(key)
            if allowed_values is None:
                raise _violation(
                    "a direction uses a property outside the exported design-system token vocabulary",  # noqa: E501
                    label=label,
                    pxg_key=pxg_key,
                    property=key,
                    allowed_properties=sorted(design_tokens),
                )
            if value not in allowed_values:
                raise _violation(
                    "a direction uses a value outside the exported design-system token vocabulary",  # noqa: E501
                    label=label,
                    pxg_key=pxg_key,
                    property=key,
                    value=value,
                    allowed_values=sorted(str(item) for item in allowed_values),
                )
            tokens[key] = value
        nodes.append(
            DesignDirectionNode(
                pxg_key=pxg_key, intent=_text(raw, "intent"), tokens=tokens
            )
        )

    return DesignDirection(
        label=label,
        summary=_text(entry, "summary"),
        rationale=_text(entry, "rationale"),
        preview_path=preview_path,
        nodes=tuple(nodes),
    )


def _text(source: Mapping[str, object], field: str) -> str:
    value = source.get(field)
    if not isinstance(value, str) or not value.strip():
        raise _violation(f"manifest field '{field}' is missing or empty")
    return value.strip()
