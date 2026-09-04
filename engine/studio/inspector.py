"""Descriptor-driven Frontend Studio Inspector (DDE-069).

The Inspector does not encode ad-hoc CSS controls. It projects the selected
candidate PXG node through the same token catalogue, lock rules, candidate
staleness and verification obligations that the mutation planner enforces.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.frontend_candidate import FrontendCandidate
from engine.contracts.frontend_lock import FrontendLock
from engine.core.errors import DdeError
from engine.studio.candidates.lifecycle import CandidateState, is_mutable
from engine.studio.candidates.service import CandidateService
from engine.studio.locks.resolution import evaluate
from engine.studio.locks.service import LockService
from engine.studio.mutations.executor import MutationExecutor
from engine.studio.pxg.service import PxgGraph
from engine.studio.tokens_catalog import STYLE_PROPERTIES, allowed_values
from engine.studio.tokens_pin import load_token_sheet


@dataclass(frozen=True)
class InspectorPropertyDescriptor:
    property_name: str
    value: str | None
    value_type: str
    units: str | None
    semantic_token_class: str
    legal_values: tuple[str, ...]
    computed_value: str | None
    responsive_semantics: str
    source_path: str | None
    mutation_operation: str
    lock_behavior: str
    writable: bool
    lock_reason: str | None
    accessibility_effect: str
    validation: str
    preview_invalidation: tuple[str, ...]
    required_verification: tuple[str, ...]


@dataclass(frozen=True)
class InspectorDescriptor:
    candidate_id: str
    pxg_key: str
    title: str
    node_kind: str
    candidate_state: str
    graph_revision: int
    stale: bool
    source_mapping: str
    source_path: str | None
    source_symbol: str | None
    element_id: str | None
    properties: tuple[InspectorPropertyDescriptor, ...]
    required_verification: tuple[str, ...]


class InspectorService:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        candidates: CandidateService | None = None,
        mutations: MutationExecutor | None = None,
        locks: LockService | None = None,
    ) -> None:
        self._engine = engine
        self._candidates = candidates or CandidateService(engine)
        self._locks = locks or LockService(engine)
        self._mutations = mutations or MutationExecutor(
            engine, candidates=self._candidates, locks=self._locks
        )

    async def describe(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
        pxg_key: str,
    ) -> InspectorDescriptor:
        # Import UUID here only for the public type conversion; keeping the
        # pure descriptor builder below UUID-agnostic makes it easy to sweep.
        from uuid import UUID

        if not all(
            isinstance(item, UUID) for item in (tenant_id, project_id, candidate_id)
        ):
            raise TypeError("tenant_id, project_id and candidate_id must be UUIDs")
        candidate_view = await self._candidates.view(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
        )
        graph = await self._mutations.candidate_graph(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
        )
        locks = await self._locks.active(tenant_id=tenant_id, project_id=project_id)
        return build_descriptor(
            candidate=candidate_view.candidate,
            graph=graph,
            locks=locks,
            pxg_key=pxg_key,
            stale=candidate_view.stale,
        )


def build_descriptor(
    *,
    candidate: FrontendCandidate,
    graph: PxgGraph,
    locks: tuple[FrontendLock, ...] | list[FrontendLock],
    pxg_key: str,
    stale: bool,
) -> InspectorDescriptor:
    node = graph.node_by_key(pxg_key)
    if node is None:
        raise DdeError(
            "CONTEXT_INCOMPLETE",
            "selected PXG node no longer exists in this candidate",
            retryable=False,
            details={"pxg_key": pxg_key},
        )
    source = node.source_refs[0] if node.source_refs else None
    source_path = source.path if source else None
    source_symbol = source.symbol if source else None
    raw_element_id = node.attributes.get("element_id")
    element_id = raw_element_id if isinstance(raw_element_id, str) else None
    if source_path and element_id:
        source_mapping = "VERIFIED"
    elif source_path:
        source_mapping = "PARTIAL"
    else:
        source_mapping = "UNAVAILABLE"

    required = _required_verification(graph, pxg_key)
    decision = evaluate(locks, target_key=pxg_key, operation="SET_PROPERTY")
    candidate_writable = is_mutable(CandidateState(candidate.state)) and not stale
    writable = candidate_writable and decision.allowed
    properties = tuple(
        _property_descriptor(
            property_name=property_name,
            value=(
                str(node.attributes[property_name])
                if isinstance(node.attributes.get(property_name), str)
                else None
            ),
            source_path=source_path,
            writable=writable,
            lock_reason=decision.reason,
            required_verification=required,
        )
        for property_name in sorted(STYLE_PROPERTIES)
    )
    return InspectorDescriptor(
        candidate_id=str(candidate.candidate_id),
        pxg_key=pxg_key,
        title=node.title,
        node_kind=node.node_kind,
        candidate_state=candidate.state,
        graph_revision=graph.revision,
        stale=stale,
        source_mapping=source_mapping,
        source_path=source_path,
        source_symbol=source_symbol,
        element_id=element_id,
        properties=properties,
        required_verification=required,
    )


def _property_descriptor(
    *,
    property_name: str,
    value: str | None,
    source_path: str | None,
    writable: bool,
    lock_reason: str | None,
    required_verification: tuple[str, ...],
) -> InspectorPropertyDescriptor:
    units = {
        "spacing": "px",
        "radius": "px",
        "type": "rem",
        "z_index": "integer",
    }.get(property_name)
    accessibility = {
        "color": "CONTRAST_RECHECK",
        "spacing": "LAYOUT_REFLOW_RECHECK",
        "type": "TEXT_SCALING_RECHECK",
    }.get(property_name, "NONE_KNOWN")
    return InspectorPropertyDescriptor(
        property_name=property_name,
        value=value,
        value_type="TOKEN",
        units=units,
        semantic_token_class=property_name,
        legal_values=tuple(sorted(allowed_values(property_name))),
        computed_value=_computed_value(property_name, value),
        responsive_semantics="GLOBAL",
        source_path=source_path,
        mutation_operation="SET_PROPERTY",
        lock_behavior="OPERATION_SENSITIVE",
        writable=writable,
        lock_reason=lock_reason if not writable else None,
        accessibility_effect=accessibility,
        validation="TOKEN_REQUIRED",
        preview_invalidation=("PREVIEW", "VISUAL_VERIFICATION"),
        required_verification=required_verification,
    )


def _computed_value(property_name: str, value: str | None) -> str | None:
    if value is None:
        return None
    raw = load_token_sheet().raw["properties"]
    locations: dict[str, tuple[str, ...]] = {
        "spacing": ("spacing", "properties"),
        "radius": ("radius", "properties"),
        "shadow": ("shadow", "properties"),
        "type": ("typography", "properties", "scale", "properties"),
        "z_index": ("zIndex", "properties"),
    }
    if property_name not in locations:
        return value
    current: object = raw
    for segment in locations[property_name]:
        if not isinstance(current, dict):
            return None
        current = current.get(segment)
    if not isinstance(current, dict):
        return None
    item = current.get(value)
    if not isinstance(item, dict) or "const" not in item:
        return None
    literal = item["const"]
    if property_name in {"spacing", "radius"}:
        return f"{literal}px"
    if property_name == "type":
        return f"{literal}rem"
    return str(literal)


def _required_verification(graph: PxgGraph, key: str) -> tuple[str, ...]:
    current = graph.node_by_key(key)
    seen: set[str] = set()
    while current is not None and current.pxg_key not in seen:
        seen.add(current.pxg_key)
        if current.node_kind == "screen":
            raw = current.attributes.get("bound_verification_kinds")
            if isinstance(raw, list):
                return tuple(sorted(str(item) for item in raw))
            return ()
        current = graph.node_by_key(current.parent_key) if current.parent_key else None
    return ()
