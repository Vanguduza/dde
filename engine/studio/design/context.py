"""DDE-069 DesignEditContext -- what may leave DDE, and nothing else.

Before any external design provider is called, the context it receives is
compiled here from an allowlist. This is the egress boundary
(FRONTEND_STUDIO_REV3 section 28.1): a provider gets the design-system
snapshot, the PXG slice for the scope being designed and the relevant
contract obligations. It does not get the repository, credentials, other
projects' nodes, or anything outside the requested scope.

The compiler produces a manifest hash alongside the context, so "what did
we send that provider?" has an answer that is a record rather than a
reconstruction.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from engine.contracts.frontend_contract import FrontendContract, Obligation
from engine.contracts.pxg_node import PxgNode
from engine.core.errors import DdeError
from engine.studio.locks.resolution import covers_key
from engine.studio.pxg.service import PxgGraph

#: Node attribute keys that may be exported. Anything else stays behind:
#: an attribute added later for an internal purpose must be admitted
#: deliberately rather than leaking because the allowlist was a denylist.
EXPORTABLE_NODE_ATTRIBUTES: Final[frozenset[str]] = frozenset(
    {
        "route",
        "state_name",
        "breakpoint",
        "spacing",
        "color",
        "radius",
        "type",
        "shadow",
        "layout",
        "direction",
        "responsive_required",
        "destructive",
    }
)

#: Provenance keys that may be exported. Deliberately excludes internal
#: identifiers such as authoring task and mission ids -- a design provider
#: has no need for DDE's mission structure.
EXPORTABLE_PROVENANCE: Final[frozenset[str]] = frozenset(
    {"source", "licence", "provider", "version"}
)

MAX_EXPORTED_NODES: Final = 400


@dataclass(frozen=True)
class DesignSystemSnapshot:
    """The allowlisted design system a provider is allowed to design with."""

    tokens: dict[str, list[str]]
    version: str

    @property
    def content_hash(self) -> str:
        payload = json.dumps(
            {"tokens": self.tokens, "version": self.version},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DesignEditContext:
    """The complete payload a design provider may receive."""

    scope_keys: tuple[str, ...]
    design_system: DesignSystemSnapshot
    nodes: tuple[dict[str, object], ...]
    obligations: tuple[dict[str, object], ...]
    pxg_revision: int
    contract_version: int | None

    @property
    def manifest(self) -> dict[str, object]:
        """A record of what was sent, by field and hash."""
        return {
            "scope_keys": list(self.scope_keys),
            "design_system_hash": self.design_system.content_hash,
            "design_system_version": self.design_system.version,
            "node_count": len(self.nodes),
            "obligation_count": len(self.obligations),
            "pxg_revision": self.pxg_revision,
            "contract_version": self.contract_version,
            "content_hash": self.content_hash,
        }

    @property
    def content_hash(self) -> str:
        payload = json.dumps(
            {
                "scope_keys": sorted(self.scope_keys),
                "design_system": self.design_system.content_hash,
                "nodes": self.nodes,
                "obligations": self.obligations,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def design_system_snapshot() -> DesignSystemSnapshot:
    """Compile the project's design system from the token catalogue.

    Tokens are exported as *names*, never as resolved literal values: a
    provider designing against `space6` produces something DDE can validate,
    whereas one designing against `24px` produces something that has already
    escaped the token discipline.
    """
    from engine.studio.tokens_catalog import STYLE_PROPERTIES, allowed_values

    return DesignSystemSnapshot(
        tokens={
            prop: sorted(allowed_values(prop)) for prop in sorted(STYLE_PROPERTIES)
        },
        version="1",
    )


def compile_context(
    *,
    scope_keys: Sequence[str],
    graph: PxgGraph,
    contract: FrontendContract | None,
    design_system: DesignSystemSnapshot | None = None,
) -> DesignEditContext:
    """Compile the minimal context for designing `scope_keys`."""
    if not scope_keys:
        raise DdeError(
            "VALIDATION_FAILED",
            "a design request must name the scope it is designing; an "
            "unscoped request would export the whole project",
            retryable=False,
        )
    in_scope = [
        node
        for node in graph.nodes
        if any(covers_key(scope, node.pxg_key) for scope in scope_keys)
    ]
    if not in_scope:
        raise DdeError(
            "CONTEXT_INCOMPLETE",
            "no PXG node falls within the requested design scope",
            retryable=False,
            details={"scope_keys": list(scope_keys)},
        )
    if len(in_scope) > MAX_EXPORTED_NODES:
        raise DdeError(
            "POLICY_DENIED",
            "design scope exceeds the export bound; narrow the selection",
            retryable=False,
            details={
                "node_count": len(in_scope),
                "maximum": MAX_EXPORTED_NODES,
            },
        )

    obligations = (
        [
            _obligation(item)
            for item in contract.obligations
            if any(covers_key(scope, item.pxg_key) for scope in scope_keys)
        ]
        if contract is not None
        else []
    )
    return DesignEditContext(
        scope_keys=tuple(scope_keys),
        design_system=design_system or design_system_snapshot(),
        nodes=tuple(_node(item) for item in in_scope),
        obligations=tuple(obligations),
        pxg_revision=graph.revision,
        contract_version=contract.contract_version if contract else None,
    )


def _node(node: PxgNode) -> dict[str, object]:
    return {
        "pxg_key": node.pxg_key,
        "node_kind": node.node_kind,
        "title": node.title,
        "parent_key": node.parent_key,
        "attributes": {
            key: value
            for key, value in node.attributes.items()
            if key in EXPORTABLE_NODE_ATTRIBUTES
        },
        "provenance": {
            key: value
            for key, value in node.provenance.items()
            if key in EXPORTABLE_PROVENANCE
        },
    }


def _obligation(obligation: Obligation) -> dict[str, object]:
    return {
        "dimension": obligation.dimension,
        "pxg_key": obligation.pxg_key,
        "statement": obligation.statement,
        "applicability": obligation.applicability,
    }
